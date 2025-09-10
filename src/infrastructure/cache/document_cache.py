"""Document-specific caching implementation using Redis"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.infrastructure.cache.redis_cache import RedisCache
from src.infrastructure.logging.logging_config import get_logger

logger = get_logger("document_cache")


class RedisDocumentCache(RedisCache):
    """Document-specific cache that extends the generic Redis cache

    This class provides specialized methods for caching Google Documents
    with structured metadata including content hashes and timestamps.
    """

    def _generate_cache_key(
        self, document_id: str, content_type: str = "content"
    ) -> str:
        """Generate cache key for document"""
        return f"gdoc:{content_type}:{document_id}"

    def _serialize_document_data(
        self, content: str, title: Optional[str] = None
    ) -> str:
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
            cached_data = self.get(cache_key)

            if cached_data is None:
                logger.debug(f"Cache miss for document: {document_id}")
                return None

            document_data = self._deserialize_document_data(cached_data)
            if not document_data:
                return None

            logger.debug(f"Cache hit for document: {document_id}")
            return document_data.get("content")

        except Exception as e:
            logger.error(
                f"Unexpected error retrieving cached document {document_id}: {e}"
            )
            return None

    def set_document_content(
        self, document_id: str, content: str, title: Optional[str] = None
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

            result = self.set(cache_key, serialized_data, self.ttl_seconds)

            if result:
                logger.debug(
                    f"Cached document {document_id} with TTL {self.ttl_hours}h"
                )
                return True

            logger.warning(f"Failed to cache document {document_id}")
            return False

        except Exception as e:
            logger.error(f"Unexpected error caching document {document_id}: {e}")
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
            cached_data = self.get(cache_key)

            if cached_data is None:
                return None

            document_data = self._deserialize_document_data(cached_data)
            return document_data.get("title")

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
            result = self.delete(cache_key)

            if result > 0:
                logger.debug(f"Invalidated cache for document: {document_id}")
                return True

            logger.debug(f"No cache entry found for document: {document_id}")
            return False

        except Exception as e:
            logger.error(
                f"Unexpected error invalidating cached document {document_id}: {e}"
            )
            return False

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get document cache statistics

        Returns:
            Dictionary with cache statistics
        """
        if not self.enabled:
            return {"enabled": False}

        try:
            gdoc_keys = self.keys("gdoc:*")

            # Get Redis info using the underlying client
            info = self.redis_client.info()

            return {
                "enabled": True,
                "total_cached_documents": len(gdoc_keys),
                "redis_memory_used": info.get("used_memory_human", "unknown"),
                "redis_connected_clients": info.get("connected_clients", 0),
                "ttl_hours": self.ttl_hours,
            }

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
            gdoc_keys = self.keys("gdoc:*")
            if gdoc_keys:
                deleted_count = self.delete(*gdoc_keys)
                logger.info(f"Cleared {deleted_count} cached documents")
                return True

            logger.info("No cached documents to clear")
            return True

        except Exception as e:
            logger.error(f"Unexpected error clearing cache: {e}")
            return False


def get_document_cache() -> RedisDocumentCache:
    """Get the singleton document cache instance

    Returns:
        RedisDocumentCache: The singleton document cache instance
    """
    return RedisDocumentCache()
