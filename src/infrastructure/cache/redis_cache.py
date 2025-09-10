"""Redis-based caching implementation with generic operations support"""

import json
from typing import Dict, List, Optional

import redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import (
    RedisError,
)

from src.common.singleton_meta import SingletonMeta
from src.infrastructure.config import get_config
from src.infrastructure.logging.logging_config import get_logger

logger = get_logger("redis_cache")


class RedisCache(metaclass=SingletonMeta):
    """Generic Redis cache with common operations

    This class implements the Singleton pattern to ensure only one
    Redis connection is maintained throughout the application lifecycle.
    Provides generic Redis operations that can be extended by specific cache types.
    """

    def __init__(self):
        """Initialize Redis connection and cache settings

        Note: Due to singleton pattern, this will only be called once
        per application lifecycle.
        """
        # Prevent re-initialization if already initialized
        if hasattr(self, "_initialized"):
            return

        config = get_config()

        self._initialized = True
        self.enabled = config.config.cache_config.enable

        if not self.enabled:
            logger.info("Redis cache disabled in configuration")
            return

        self.ttl_hours = config.config.cache_config.ttl_hours
        self.ttl_seconds = self.ttl_hours * 3600

        try:
            self.redis_client = redis.Redis(
                host=config.config.cache_config.host,
                port=config.config.cache_config.port,
                db=0,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                password=config.config.cache_config.password,
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"Redis cache initialized with TTL: {self.ttl_hours} hours")
        except RedisConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.enabled = False
        except Exception as e:
            logger.error(f"Redis initialization error: {e}")
            self.enabled = False

    # =============================================================================
    # GENERIC REDIS OPERATIONS
    # =============================================================================

    def get(self, key: str) -> Optional[str]:
        """Get value by key"""
        if not self.enabled:
            return None
        try:
            return self.redis_client.get(key)
        except RedisError as e:
            logger.error(f"Redis get error for key {key}: {e}")
            return None

    def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Set key-value with optional TTL"""
        if not self.enabled:
            return False
        try:
            if ttl:
                return bool(self.redis_client.setex(key, ttl, value))
            else:
                return bool(self.redis_client.set(key, value))
        except RedisError as e:
            logger.error(f"Redis set error for key {key}: {e}")
            return False

    def delete(self, *keys: str) -> int:
        """Delete one or more keys"""
        if not self.enabled:
            return 0
        try:
            return self.redis_client.delete(*keys)
        except RedisError as e:
            logger.error(f"Redis delete error for keys {keys}: {e}")
            return 0

    def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self.enabled:
            return False
        try:
            return bool(self.redis_client.exists(key))
        except RedisError as e:
            logger.error(f"Redis exists error for key {key}: {e}")
            return False

    def keys(self, pattern: str) -> List[str]:
        """Get keys matching pattern"""
        if not self.enabled:
            return []
        try:
            return self.redis_client.keys(pattern)
        except RedisError as e:
            logger.error(f"Redis keys error for pattern {pattern}: {e}")
            return []

    def expire(self, key: str, ttl: int) -> bool:
        """Set TTL for existing key"""
        if not self.enabled:
            return False
        try:
            return bool(self.redis_client.expire(key, ttl))
        except RedisError as e:
            logger.error(f"Redis expire error for key {key}: {e}")
            return False

    def get_json(self, key: str) -> Optional[Dict]:
        """Get and deserialize JSON value"""
        value = self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error for key {key}: {e}")
        return None

    def set_json(self, key: str, value: Dict, ttl: Optional[int] = None) -> bool:
        """Serialize and set JSON value"""
        try:
            json_str = json.dumps(value)
            return self.set(key, json_str, ttl)
        except (TypeError, ValueError) as e:
            logger.error(f"JSON encode error for key {key}: {e}")
            return False

    def hash_get(self, key: str, field: str) -> Optional[str]:
        """Get hash field value"""
        if not self.enabled:
            return None
        try:
            return self.redis_client.hget(key, field)
        except RedisError as e:
            logger.error(f"Redis hget error for {key}.{field}: {e}")
            return None

    def hash_set(self, key: str, field: str, value: str) -> bool:
        """Set hash field value"""
        if not self.enabled:
            return False
        try:
            return bool(self.redis_client.hset(key, field, value))
        except RedisError as e:
            logger.error(f"Redis hset error for {key}.{field}: {e}")
            return False

    def hash_get_all(self, key: str) -> Dict[str, str]:
        """Get all hash fields"""
        if not self.enabled:
            return {}
        try:
            return self.redis_client.hgetall(key)
        except RedisError as e:
            logger.error(f"Redis hgetall error for key {key}: {e}")
            return {}

    def hash_delete(self, key: str, *fields: str) -> int:
        """Delete hash fields"""
        if not self.enabled:
            return 0
        try:
            return self.redis_client.hdel(key, *fields)
        except RedisError as e:
            logger.error(f"Redis hdel error for {key}: {e}")
            return 0


def get_cache() -> RedisCache:
    """Get the singleton cache instance

    Returns:
        RedisCache: The singleton cache instance
    """
    return RedisCache()
