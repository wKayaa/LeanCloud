"""
Test Redis health checks and graceful degradation
"""

import asyncio
from app.core.redis_manager import RedisManager


async def test_redis_degraded_mode():
    """Test Redis manager in degraded mode (USE_REDIS=false)"""
    redis_manager = RedisManager("redis://localhost:6379/0", use_redis=False)
    
    # Should not initialize Redis client
    await redis_manager.initialize()
    assert redis_manager.client is None
    
    # Health check should return False when disabled
    health = await redis_manager.is_healthy()
    assert health is False
    
    # Operations should gracefully handle disabled state
    result = await redis_manager.set("test_key", "test_value")
    assert result is False
    
    value = await redis_manager.get("test_key")
    assert value is None
    
    # Publish should not fail but return 0
    published = await redis_manager.publish("test_channel", {"test": "data"})
    assert published == 0
    
    print("Redis degraded mode test passed!")


async def test_redis_enabled_mode_without_server():
    """Test Redis manager with USE_REDIS=true but no Redis server"""
    redis_manager = RedisManager("redis://localhost:9999/0", use_redis=True)  # Wrong port
    
    # Initialize should not raise exception
    await redis_manager.initialize()
    
    # Health check should return False
    health = await redis_manager.is_healthy()
    assert health is False
    
    # Operations should gracefully fail
    result = await redis_manager.set("test_key", "test_value")
    assert result is False
    
    # Publish should handle errors gracefully
    published = await redis_manager.publish("test_channel", {"test": "data"})
    assert published == 0
    
    print("Redis error handling test passed!")


if __name__ == "__main__":
    asyncio.run(test_redis_degraded_mode())
    asyncio.run(test_redis_enabled_mode_without_server())
    print("All Redis health tests passed!")