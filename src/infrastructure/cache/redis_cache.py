"""Redis-based caching implementation for Google Docs content"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import (
    RedisError,
)

from src import config
from src.common.singleton_meta import SingletonMeta
from src.infrastructure.logging.logging_config import get_logger

logger = get_logger("redis_cache")


class RedisDocumentCache(metaclass=SingletonMeta):
    """Redis-based cache for Google Documents with TTL support

    This class implements the Singleton pattern to ensure only one
    Redis connection is maintained throughout the application lifecycle.
    """

    def __init__(self):
        """Initialize Redis connection and cache settings

        Note: Due to singleton pattern, this will only be called once
        per application lifecycle.
        """
        # Prevent re-initialization if already initialized
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self.enabled = getattr(config.config, "cache_config", {}).get(
            "enabled", False
        )
        if not self.enabled:
            logger.info("Redis cache disabled in configuration")
            return

        self.ttl_hours = getattr(config.config, "cache_config", {}).get(
            "ttl_hours", 24
        )
        self.ttl_seconds = self.ttl_hours * 3600

        try:
            self.redis_client = redis.Redis(
                host=getattr(config.config, "cache_config", {}).get(
                    "host", "localhost"
                ),
                port=getattr(config.config, "cache_config", {}).get(
                    "port", 6379
                ),
                db=0,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                password=getattr(config.config, "cache_config", {}).get(
                    "password", None
                ),
            )
            # Test connection
            self.redis_client.ping()
            logger.info(
                f"Redis cache initialized with TTL: {self.ttl_hours} hours"
            )
        except RedisConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.enabled = False
        except Exception as e:
            logger.error(f"Redis initialization error: {e}")
            self.enabled = False

    def _generate_cache_key(
        self, document_id: str, content_type: str = "content"
    ) -> str:
        """Generate cache key for document"""
        return f"gdoc:{content_type}:{document_id}"

    def _serialize_document_data(self, content: str, title: str = None) -> str:
        """Serialize document data for storage"""
        data = {
            "content": content,
            "title": title,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "content_hash": hashlib.md5(content.encode()).hexdigest(),
        }
        return json.dumps(data)

    def _deserialize_document_data(self, cached_data: str) -> Dict[str, Any]:
        """Deserialize document data from storage"""
        try:
            return json.loads(cached_data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to deserialize cached data: {e}")
            return {}

    def get_document_content(self, document_id: str) -> Optional[str]:
        """
        Retrieve document content from cache

        Args:
            document_id: Google Doc ID

        Returns:
            Document content if found and valid, None otherwise
        """
        if not self.enabled:
            return None

        try:
            cache_key = self._generate_cache_key(document_id)
            cached_data = self.redis_client.get(cache_key)

            if cached_data is None:
                logger.debug(f"Cache miss for document: {document_id}")
                return None

            document_data = self._deserialize_document_data(cached_data)
            if not document_data:
                return None

            logger.debug(f"Cache hit for document: {document_id}")
            return document_data.get("content")

        except RedisError as e:
            logger.error(f"Redis error retrieving document {document_id}: {e}")
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error retrieving cached document {document_id}: {e}"
            )
            return None

    def set_document_content(
        self, document_id: str, content: str, title: str = None
    ) -> bool:
        """
        Store document content in cache

        Args:
            document_id: Google Doc ID
            content: Document text content
            title: Document title (optional)

        Returns:
            True if successfully cached, False otherwise
        """
        if not self.enabled:
            return False

        try:
            cache_key = self._generate_cache_key(document_id)
            serialized_data = self._serialize_document_data(content, title)

            result = self.redis_client.setex(
                cache_key, self.ttl_seconds, serialized_data
            )

            if result:
                logger.debug(
                    f"Cached document {document_id} with TTL {self.ttl_hours}h"
                )
                return True

            logger.warning(f"Failed to cache document {document_id}")
            return False

        except RedisError as e:
            logger.error(f"Redis error caching document {document_id}: {e}")
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error caching document {document_id}: {e}"
            )
            return False

    def get_document_title(self, document_id: str) -> Optional[str]:
        """
        Retrieve document title from cache

        Args:
            document_id: Google Doc ID

        Returns:
            Document title if found, None otherwise
        """
        if not self.enabled:
            return None

        try:
            cache_key = self._generate_cache_key(document_id)
            cached_data = self.redis_client.get(cache_key)

            if cached_data is None:
                return None

            document_data = self._deserialize_document_data(cached_data)
            return document_data.get("title")

        except RedisError as e:
            logger.error(
                f"Redis error retrieving title for {document_id}: {e}"
            )
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error retrieving cached title for {document_id}: {e}"
            )
            return None

    def invalidate_document(self, document_id: str) -> bool:
        """
        Remove document from cache

        Args:
            document_id: Google Doc ID

        Returns:
            True if successfully removed, False otherwise
        """
        if not self.enabled:
            return False

        try:
            cache_key = self._generate_cache_key(document_id)
            result = self.redis_client.delete(cache_key)

            if result > 0:
                logger.debug(f"Invalidated cache for document: {document_id}")
                return True

            logger.debug(f"No cache entry found for document: {document_id}")
            return False

        except RedisError as e:
            logger.error(
                f"Redis error invalidating document {document_id}: {e}"
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error invalidating cached document {document_id}: {e}"
            )
            return False

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics

        Returns:
            Dictionary with cache statistics
        """
        if not self.enabled:
            return {"enabled": False}

        try:
            info = self.redis_client.info()
            gdoc_keys = self.redis_client.keys("gdoc:*")

            return {
                "enabled": True,
                "total_cached_documents": len(gdoc_keys),
                "redis_memory_used": info.get("used_memory_human", "unknown"),
                "redis_connected_clients": info.get("connected_clients", 0),
                "ttl_hours": self.ttl_hours,
            }

        except RedisError as e:
            logger.error(f"Redis error getting stats: {e}")
            return {"enabled": True, "error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error getting cache stats: {e}")
            return {"enabled": True, "error": str(e)}

    def clear_all_documents(self) -> bool:
        """
        Clear all cached documents

        Returns:
            True if successfully cleared, False otherwise
        """
        if not self.enabled:
            return False

        try:
            gdoc_keys = self.redis_client.keys("gdoc:*")
            if gdoc_keys:
                deleted_count = self.redis_client.delete(*gdoc_keys)
                logger.info(f"Cleared {deleted_count} cached documents")
                return True

            logger.info("No cached documents to clear")
            return True

        except RedisError as e:
            logger.error(f"Redis error clearing cache: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error clearing cache: {e}")
            return False


def get_cache() -> RedisDocumentCache:
    """Get the singleton cache instance

    Returns:
        RedisDocumentCache: The singleton cache instance
    """
    return RedisDocumentCache()
