"""Redis manager for caching, queuing, and pub/sub with in-process fallback"""

import asyncio
import json
import time
from typing import Optional, Dict, Any, List, Set, Callable
import redis.asyncio as redis
from redis.asyncio import ConnectionPool
import structlog

logger = structlog.get_logger()


class InProcessEventBus:
    """In-memory event bus for when Redis is unavailable"""
    
    def __init__(self):
        self.channels: Dict[str, Set[Callable]] = {}
        self.pattern_channels: Dict[str, Set[Callable]] = {}
    
    async def publish(self, channel: str, message: Any) -> int:
        """Publish message to channel"""
        subscriber_count = 0
        
        # Direct channel subscriptions
        if channel in self.channels:
            for callback in self.channels[channel]:
                try:
                    await callback(channel, message)
                    subscriber_count += 1
                except Exception as e:
                    logger.warning("Failed to deliver in-process message", 
                                 channel=channel, error=str(e))
        
        # Pattern subscriptions
        for pattern, callbacks in self.pattern_channels.items():
            if self._match_pattern(pattern, channel):
                for callback in callbacks:
                    try:
                        await callback(channel, message)
                        subscriber_count += 1
                    except Exception as e:
                        logger.warning("Failed to deliver in-process pattern message",
                                     pattern=pattern, channel=channel, error=str(e))
        
        return subscriber_count
    
    def subscribe(self, channel: str, callback: Callable):
        """Subscribe to a channel"""
        if channel not in self.channels:
            self.channels[channel] = set()
        self.channels[channel].add(callback)
    
    def psubscribe(self, pattern: str, callback: Callable):
        """Subscribe to a pattern"""
        if pattern not in self.pattern_channels:
            self.pattern_channels[pattern] = set()
        self.pattern_channels[pattern].add(callback)
    
    def unsubscribe(self, channel: str, callback: Callable):
        """Unsubscribe from a channel"""
        if channel in self.channels:
            self.channels[channel].discard(callback)
            if not self.channels[channel]:
                del self.channels[channel]
    
    def punsubscribe(self, pattern: str, callback: Callable):
        """Unsubscribe from a pattern"""
        if pattern in self.pattern_channels:
            self.pattern_channels[pattern].discard(callback)
            if not self.pattern_channels[pattern]:
                del self.pattern_channels[pattern]
    
    def _match_pattern(self, pattern: str, channel: str) -> bool:
        """Simple pattern matching (supports * at end)"""
        if pattern.endswith('*'):
            return channel.startswith(pattern[:-1])
        return pattern == channel
    
    def get_subscriber_count(self, channel: str) -> int:
        """Get subscriber count for a channel"""
        count = len(self.channels.get(channel, set()))
        
        # Add pattern subscribers
        for pattern in self.pattern_channels:
            if self._match_pattern(pattern, channel):
                count += len(self.pattern_channels[pattern])
        
        return count


class MockPubSub:
    """Mock PubSub that uses in-process event bus"""
    
    def __init__(self, event_bus: InProcessEventBus, channels: List[str]):
        self.event_bus = event_bus
        self.channels = channels
        self.closed = False
        self.message_queue = asyncio.Queue()
        self.callbacks = {}
    
    async def subscribe(self, *channels: str):
        """Subscribe to additional channels"""
        for channel in channels:
            if channel not in self.channels:
                self.channels.append(channel)
            
            async def callback(ch, msg):
                if not self.closed:
                    await self.message_queue.put({
                        'type': 'message',
                        'channel': ch,
                        'data': json.dumps(msg) if not isinstance(msg, str) else msg
                    })
            
            self.callbacks[channel] = callback
            self.event_bus.subscribe(channel, callback)
    
    async def listen(self):
        """Listen for messages"""
        # Auto-subscribe to initial channels
        if not self.callbacks:
            await self.subscribe(*self.channels)
        
        while not self.closed:
            try:
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                yield message
            except asyncio.TimeoutError:
                continue
    
    async def close(self):
        """Close the pubsub"""
        self.closed = True
        for channel, callback in self.callbacks.items():
            self.event_bus.unsubscribe(channel, callback)


class RedisManager:
    """Redis manager for async operations with in-process fallback"""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.pool: Optional[ConnectionPool] = None
        self.client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        
        # Fallback event bus
        self.fallback_bus = InProcessEventBus()
        self.is_redis_available = False
        self.last_redis_check = 0.0
        self.redis_retry_interval = 30.0  # Check Redis availability every 30 seconds
        
        # In-memory cache for when Redis is down
        self.memory_cache: Dict[str, Any] = {}
        self.cache_timestamps: Dict[str, float] = {}
        
    async def initialize(self):
        """Initialize Redis connection with quiet error handling"""
        try:
            self.pool = ConnectionPool.from_url(
                self.redis_url,
                max_connections=20,
                decode_responses=True,
                health_check_interval=30,
                socket_connect_timeout=5,  # Fail fast
                socket_timeout=5
            )
            
            self.client = redis.Redis(connection_pool=self.pool)
            
            # Test connection
            await asyncio.wait_for(self.client.ping(), timeout=3.0)
            self.is_redis_available = True
            logger.info("Redis connection initialized", url=self._safe_url())
            
        except Exception as e:
            self.is_redis_available = False
            self.last_redis_check = time.time()
            # Only log once at startup, then use periodic health checks
            logger.warning("Redis unavailable, using in-process fallback", 
                         error=str(e), url=self._safe_url())
    
    def _safe_url(self) -> str:
        """Return Redis URL without credentials for logging"""
        try:
            if '://' in self.redis_url:
                scheme, rest = self.redis_url.split('://', 1)
                if '@' in rest:
                    _, host_part = rest.split('@', 1)
                    return f"{scheme}://***@{host_part}"
            return self.redis_url
        except:
            return "redis://***"
    
    async def _check_redis_health(self) -> bool:
        """Periodically check Redis health with backoff"""
        now = time.time()
        if now - self.last_redis_check < self.redis_retry_interval:
            return self.is_redis_available
        
        if not self.is_redis_available:
            try:
                if not self.client:
                    await self.initialize()
                else:
                    await asyncio.wait_for(self.client.ping(), timeout=2.0)
                
                self.is_redis_available = True
                logger.info("Redis connection restored")
                
            except Exception:
                # Quiet failure - don't spam logs
                self.is_redis_available = False
            
            self.last_redis_check = now
        
        return self.is_redis_available
    
    async def close(self):
        """Close Redis connection"""
        if self.pubsub:
            await self.pubsub.close()
        if self.client:
            await self.client.close()
        if self.pool:
            await self.pool.disconnect()
        logger.info("Redis connection closed")
    
    # Cache operations with fallback
    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Set a key-value pair with optional expiration"""
        try:
            if await self._check_redis_health():
                serialized = json.dumps(value) if not isinstance(value, str) else value
                return await self.client.set(key, serialized, ex=ex)
        except Exception as e:
            logger.debug("Redis SET failed, using memory cache", key=key, error=str(e))
        
        # Fallback to memory cache
        self.memory_cache[key] = value
        if ex:
            self.cache_timestamps[key] = time.time() + ex
        return True
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value by key"""
        try:
            if await self._check_redis_health():
                value = await self.client.get(key)
                if value is None:
                    return None
                
                # Try to deserialize as JSON, fallback to string
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
        except Exception as e:
            logger.debug("Redis GET failed, using memory cache", key=key, error=str(e))
        
        # Fallback to memory cache
        if key in self.memory_cache:
            # Check expiration
            if key in self.cache_timestamps:
                if time.time() > self.cache_timestamps[key]:
                    self.memory_cache.pop(key, None)
                    self.cache_timestamps.pop(key, None)
                    return None
            return self.memory_cache[key]
        
        return None
    
    async def delete(self, key: str) -> bool:
        """Delete a key"""
        try:
            return bool(await self.client.delete(key))
        except Exception as e:
            logger.error("Redis DELETE failed", key=key, error=str(e))
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        try:
            return bool(await self.client.exists(key))
        except Exception as e:
            logger.error("Redis EXISTS failed", key=key, error=str(e))
            return False
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration for a key"""
        try:
            return bool(await self.client.expire(key, seconds))
        except Exception as e:
            logger.error("Redis EXPIRE failed", key=key, error=str(e))
            return False
    
    # Hash operations
    async def hset(self, key: str, field: str, value: Any) -> bool:
        """Set hash field"""
        try:
            serialized = json.dumps(value) if not isinstance(value, str) else value
            return bool(await self.client.hset(key, field, serialized))
        except Exception as e:
            logger.error("Redis HSET failed", key=key, field=field, error=str(e))
            return False
    
    async def hget(self, key: str, field: str) -> Optional[Any]:
        """Get hash field"""
        try:
            value = await self.client.hget(key, field)
            if value is None:
                return None
            
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error("Redis HGET failed", key=key, field=field, error=str(e))
            return None
    
    async def hgetall(self, key: str) -> Dict[str, Any]:
        """Get all hash fields"""
        try:
            data = await self.client.hgetall(key)
            result = {}
            for field, value in data.items():
                try:
                    result[field] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    result[field] = value
            return result
        except Exception as e:
            logger.error("Redis HGETALL failed", key=key, error=str(e))
            return {}
    
    async def hdel(self, key: str, field: str) -> bool:
        """Delete hash field"""
        try:
            return bool(await self.client.hdel(key, field))
        except Exception as e:
            logger.error("Redis HDEL failed", key=key, field=field, error=str(e))
            return False
    
    # List operations
    async def lpush(self, key: str, *values: Any) -> int:
        """Push values to the left of a list"""
        try:
            serialized = [json.dumps(v) if not isinstance(v, str) else v for v in values]
            return await self.client.lpush(key, *serialized)
        except Exception as e:
            logger.error("Redis LPUSH failed", key=key, error=str(e))
            return 0
    
    async def rpop(self, key: str) -> Optional[Any]:
        """Pop value from the right of a list"""
        try:
            value = await self.client.rpop(key)
            if value is None:
                return None
            
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error("Redis RPOP failed", key=key, error=str(e))
            return None
    
    async def llen(self, key: str) -> int:
        """Get list length"""
        try:
            return await self.client.llen(key)
        except Exception as e:
            logger.error("Redis LLEN failed", key=key, error=str(e))
            return 0
    
    # Set operations
    async def sadd(self, key: str, *values: Any) -> int:
        """Add values to a set"""
        try:
            serialized = [json.dumps(v) if not isinstance(v, str) else v for v in values]
            return await self.client.sadd(key, *serialized)
        except Exception as e:
            logger.error("Redis SADD failed", key=key, error=str(e))
            return 0
    
    async def srem(self, key: str, *values: Any) -> int:
        """Remove values from a set"""
        try:
            serialized = [json.dumps(v) if not isinstance(v, str) else v for v in values]
            return await self.client.srem(key, *serialized)
        except Exception as e:
            logger.error("Redis SREM failed", key=key, error=str(e))
            return 0
    
    async def smembers(self, key: str) -> List[Any]:
        """Get all set members"""
        try:
            values = await self.client.smembers(key)
            result = []
            for value in values:
                try:
                    result.append(json.loads(value))
                except (json.JSONDecodeError, TypeError):
                    result.append(value)
            return result
        except Exception as e:
            logger.error("Redis SMEMBERS failed", key=key, error=str(e))
            return []
    
    async def sismember(self, key: str, value: Any) -> bool:
        """Check if value is in set"""
        try:
            serialized = json.dumps(value) if not isinstance(value, str) else value
            return bool(await self.client.sismember(key, serialized))
        except Exception as e:
            logger.error("Redis SISMEMBER failed", key=key, error=str(e))
            return False
    
    # Pub/Sub operations with fallback
    async def publish(self, channel: str, message: Any) -> int:
        """Publish message to channel with fallback"""
        try:
            if await self._check_redis_health():
                serialized = json.dumps(message) if not isinstance(message, str) else message
                return await self.client.publish(channel, serialized)
        except Exception as e:
            logger.debug("Redis publish failed, using fallback", channel=channel, error=str(e))
        
        # Fallback to in-process bus
        return await self.fallback_bus.publish(channel, message)
    
    def subscribe_fallback(self, channel: str, callback: Callable):
        """Subscribe to channel using fallback bus"""
        self.fallback_bus.subscribe(channel, callback)
    
    def psubscribe_fallback(self, pattern: str, callback: Callable):
        """Subscribe to pattern using fallback bus"""
        self.fallback_bus.psubscribe(pattern, callback)
    
    def unsubscribe_fallback(self, channel: str, callback: Callable):
        """Unsubscribe from fallback bus"""
        self.fallback_bus.unsubscribe(channel, callback)
    
    async def subscribe_with_fallback(self, *channels: str):
        """Subscribe to channels with Redis or fallback"""
        try:
            if await self._check_redis_health():
                pubsub = self.client.pubsub()
                await pubsub.subscribe(*channels)
                return pubsub
        except Exception as e:
            logger.debug("Redis subscribe failed", channels=channels, error=str(e))
        
        # Return a mock pubsub that uses fallback
        return MockPubSub(self.fallback_bus, list(channels))
    
    async def subscribe(self, *channels: str) -> redis.client.PubSub:
        """Subscribe to channels (Redis only - legacy method)"""
        if not await self._check_redis_health():
            raise RuntimeError("Redis not available")
        
        pubsub = self.client.pubsub()
        await pubsub.subscribe(*channels)
        return pubsub
    
    # Rate limiting with fallback
    async def rate_limit(self, key: str, limit: int, window: int) -> bool:
        """Check rate limit using sliding window with fallback"""
        try:
            if await self._check_redis_health():
                current_time = int(time.time())
                pipe = self.client.pipeline()
                
                # Remove old entries
                pipe.zremrangebyscore(key, 0, current_time - window)
                # Add current request
                pipe.zadd(key, {str(current_time): current_time})
                # Count requests in window
                pipe.zcount(key, current_time - window, current_time)
                # Set expiration
                pipe.expire(key, window)
                
                results = await pipe.execute()
                count = results[2]
                
                return count <= limit
        except Exception as e:
            logger.debug("Redis rate limit failed, using memory fallback", key=key, error=str(e))
        
        # Fallback to memory-based rate limiting
        if not hasattr(self, 'rate_limit_memory'):
            self.rate_limit_memory = {}
        
        current_time = time.time()
        if key not in self.rate_limit_memory:
            self.rate_limit_memory[key] = []
        
        # Clean old entries
        self.rate_limit_memory[key] = [
            t for t in self.rate_limit_memory[key] 
            if t > current_time - window
        ]
        
        # Check limit
        if len(self.rate_limit_memory[key]) >= limit:
            return False
        
        # Add current request
        self.rate_limit_memory[key].append(current_time)
        return True
    
    # Atomic operations
    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment key value atomically"""
        try:
            return await self.client.incr(key, amount)
        except Exception as e:
            logger.error("Redis INCR failed", key=key, error=str(e))
            return 0
    
    async def decr(self, key: str, amount: int = 1) -> int:
        """Decrement key value atomically"""
        try:
            return await self.client.decr(key, amount)
        except Exception as e:
            logger.error("Redis DECR failed", key=key, error=str(e))
            return 0
    
    # Scan queue operations (for high concurrency)
    async def enqueue_scan_urls(self, scan_id: str, urls: List[str], priority: int = 0) -> bool:
        """Enqueue URLs for scanning with priority"""
        try:
            queue_key = f"scan_queue:{scan_id}"
            pipe = self.client.pipeline()
            
            for url in urls:
                pipe.zadd(queue_key, {url: priority})
            
            await pipe.execute()
            return True
        except Exception as e:
            logger.error("Failed to enqueue scan URLs", scan_id=scan_id, error=str(e))
            return False
    
    async def dequeue_scan_urls(self, scan_id: str, count: int = 100) -> List[str]:
        """Dequeue URLs for scanning"""
        try:
            queue_key = f"scan_queue:{scan_id}"
            # Get highest priority URLs
            urls = await self.client.zrevrange(queue_key, 0, count - 1)
            if urls:
                # Remove them from the queue
                await self.client.zrem(queue_key, *urls)
            return urls
        except Exception as e:
            logger.error("Failed to dequeue scan URLs", scan_id=scan_id, error=str(e))
            return []
    
    async def get_queue_size(self, scan_id: str) -> int:
        """Get scan queue size"""
        try:
            queue_key = f"scan_queue:{scan_id}"
            return await self.client.zcard(queue_key)
        except Exception as e:
            logger.error("Failed to get queue size", scan_id=scan_id, error=str(e))
            return 0


# Global Redis manager instance
redis_manager: Optional[RedisManager] = None


async def init_redis(redis_url: str):
    """Initialize Redis connection"""
    global redis_manager
    redis_manager = RedisManager(redis_url)
    await redis_manager.initialize()


async def close_redis():
    """Close Redis connection"""
    global redis_manager
    if redis_manager:
        await redis_manager.close()
        redis_manager = None


def get_redis() -> RedisManager:
    """Get Redis manager instance"""
    if not redis_manager:
        raise RuntimeError("Redis manager not initialized")
    return redis_manager