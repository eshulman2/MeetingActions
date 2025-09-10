"""Cache infrastructure module

This module provides Redis-based caching capabilities with both generic
operations and specialized document caching.
"""

from src.infrastructure.cache.document_cache import (
    RedisDocumentCache,
    get_document_cache,
)
from src.infrastructure.cache.redis_cache import RedisCache, get_cache

# Backward compatibility - maintain existing imports
__all__ = ["RedisCache", "RedisDocumentCache", "get_cache", "get_document_cache"]
