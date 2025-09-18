"""Redis manager for caching, queuing, and pub/sub"""

import asyncio
import json
from typing import Optional, Dict, Any, List
import redis.asyncio as redis
from redis.asyncio import ConnectionPool
import structlog

logger = structlog.get_logger()


class RedisManager:
    """Redis manager for async operations with graceful degradation"""
    
    def __init__(self, redis_url: str, use_redis: bool = True):
        self.redis_url = redis_url
        self.use_redis = use_redis
        self.pool: Optional[ConnectionPool] = None
        self.client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self._healthy = False
        self._last_health_check = 0
        self._health_check_interval = 30  # seconds
        
        if not use_redis:
            logger.info("Redis manager initialized in disabled mode")
        
    async def initialize(self):
        """Initialize Redis connection with retry logic"""
        if not self.use_redis:
            logger.info("Redis initialization skipped - USE_REDIS=false")
            return
            
        try:
            self.pool = ConnectionPool.from_url(
                self.redis_url,
                max_connections=20,
                decode_responses=True,
                health_check_interval=30,
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            self.client = redis.Redis(connection_pool=self.pool)
            
            # Test connection
            await self.client.ping()
            self._healthy = True
            self._last_health_check = asyncio.get_event_loop().time()
            logger.info("Redis connection initialized", url=self.redis_url)
            
        except Exception as e:
            self._healthy = False
            logger.error("Failed to initialize Redis", error=str(e))
            # Don't raise - allow application to continue in degraded mode
    
    async def is_healthy(self) -> bool:
        """Check if Redis connection is healthy"""
        if not self.use_redis:
            return False
            
        current_time = asyncio.get_event_loop().time()
        
        # Check if we need to refresh health status
        if current_time - self._last_health_check > self._health_check_interval:
            try:
                if self.client:
                    await self.client.ping()
                    self._healthy = True
                else:
                    self._healthy = False
            except Exception:
                self._healthy = False
            finally:
                self._last_health_check = current_time
        
        return self._healthy
    
    async def close(self):
        """Close Redis connection"""
        if self.pubsub:
            await self.pubsub.close()
        if self.client:
            await self.client.close()
        if self.pool:
            await self.pool.disconnect()
        logger.info("Redis connection closed")
    
    # Cache operations
    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Set a key-value pair with optional expiration"""
        if not self.use_redis or not await self.is_healthy():
            return False
        try:
            serialized = json.dumps(value) if not isinstance(value, str) else value
            return await self.client.set(key, serialized, ex=ex)
        except Exception as e:
            logger.error("Redis SET failed", key=key, error=str(e))
            return False
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value by key"""
        if not self.use_redis or not await self.is_healthy():
            return None
        try:
            value = await self.client.get(key)
            if value is None:
                return None
            
            # Try to deserialize as JSON, fallback to string
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error("Redis GET failed", key=key, error=str(e))
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
    
    # Pub/Sub operations
    async def publish(self, channel: str, message: Any) -> int:
        """Publish message to channel with graceful degradation"""
        if not await self.is_healthy():
            logger.warning("Redis PUBLISH skipped - Redis unavailable", channel=channel)
            return 0
        
        try:
            serialized = json.dumps(message) if not isinstance(message, str) else message
            return await self.client.publish(channel, serialized)
        except Exception as e:
            logger.error("Redis PUBLISH failed", channel=channel, error=str(e))
            self._healthy = False
            return 0
    
    async def subscribe(self, *channels: str) -> Optional[redis.client.PubSub]:
        """Subscribe to channels with graceful degradation"""
        if not await self.is_healthy():
            logger.warning("Redis SUBSCRIBE skipped - Redis unavailable", channels=channels)
            return None
        
        try:
            pubsub = self.client.pubsub()
            await pubsub.subscribe(*channels)
            return pubsub
        except Exception as e:
            logger.error("Redis SUBSCRIBE failed", channels=channels, error=str(e))
            self._healthy = False
            return None
    
    # Rate limiting
    async def rate_limit(self, key: str, limit: int, window: int) -> bool:
        """Check rate limit using sliding window with graceful degradation"""
        if not await self.is_healthy():
            logger.warning("Redis rate limit check skipped - Redis unavailable", key=key)
            return True  # Allow requests when Redis is down
        
        try:
            current_time = int(asyncio.get_event_loop().time())
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
            logger.error("Redis rate limit failed", key=key, error=str(e))
            self._healthy = False
            return True  # Allow on error
    
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


async def init_redis(redis_url: str, use_redis: bool = True):
    """Initialize Redis connection with graceful degradation support"""
    global redis_manager
    
    if not use_redis:
        logger.info("Redis disabled - running in degraded mode", use_redis=use_redis)
        redis_manager = RedisManager(redis_url, use_redis=False)
        return
    
    redis_manager = RedisManager(redis_url, use_redis=True)
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
        # Return a dummy Redis manager for graceful degradation
        return RedisManager("redis://localhost:6379", use_redis=False)
    return redis_manager