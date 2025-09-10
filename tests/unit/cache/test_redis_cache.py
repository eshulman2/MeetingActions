"""
Unit tests for Redis cache functionality.
"""

from unittest.mock import Mock, patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError

from src.infrastructure.cache import RedisDocumentCache, get_document_cache


@pytest.mark.unit
@pytest.mark.redis
class TestRedisDocumentCache:
    """Test RedisDocumentCache functionality."""

    def test_singleton_behavior(self, mock_redis):
        """Test that RedisDocumentCache follows singleton pattern."""
        cache1 = RedisDocumentCache()
        cache2 = RedisDocumentCache()

        assert cache1 is cache2
        assert id(cache1) == id(cache2)

    def test_cache_disabled_in_config(self, test_config):
        """Test cache behavior when disabled in config."""
        test_config.cache_config.enable = False

        with patch(
            "src.infrastructure.cache.redis_cache.get_config",
            return_value=Mock(config=test_config),
        ):
            cache = RedisDocumentCache()

            assert cache.enabled is False
            assert cache.get_document_content("test_id") is None
            assert cache.set_document_content("test_id", "content") is False

    def test_cache_enabled_successful_connection(self, mock_redis, test_config):
        """Test cache initialization with successful Redis connection."""
        test_config.cache_config.enable = True
        test_config.cache_config.password = "test_password"

        with patch(
            "src.infrastructure.cache.redis_cache.get_config",
            return_value=Mock(config=test_config),
        ):
            cache = RedisDocumentCache()

            assert cache.enabled is True
            assert cache.ttl_hours == 1
            assert cache.ttl_seconds == 3600

    def test_cache_connection_error(self, test_config):
        """Test cache initialization with Redis connection error."""
        test_config.cache_config.enable = True
        test_config.cache_config.password = "test_password"

        with patch(
            "src.infrastructure.cache.redis_cache.get_config",
            return_value=Mock(config=test_config),
        ):
            with patch("redis.Redis") as mock_redis_class:
                mock_redis_instance = Mock()
                mock_redis_instance.ping.side_effect = RedisConnectionError(
                    "Connection failed"
                )
                mock_redis_class.return_value = mock_redis_instance

                cache = RedisDocumentCache()

                assert cache.enabled is False

    def test_set_document_content_success(
        self, mock_redis, test_config, reset_singletons
    ):
        """Test successful document content caching."""
        test_config.cache_config.enable = True
        test_config.cache_config.password = "test_password"

        with patch(
            "src.infrastructure.cache.redis_cache.get_config",
            return_value=Mock(config=test_config),
        ), patch(
            "src.infrastructure.cache.redis_cache.redis.Redis", return_value=mock_redis
        ):
            cache = RedisDocumentCache()

            # Mock the Redis setex method to return True
            mock_redis.setex = Mock(return_value=True)

            result = cache.set_document_content("doc123", "Test content", "Test Title")

            assert result is True
            # Verify setex was called with the document ID
            mock_redis.setex.assert_called_once()

    def test_get_document_content_hit(self, mock_redis, test_config, reset_singletons):
        """Test cache hit for document content."""
        test_config.cache_config.enable = True
        test_config.cache_config.password = "test_password"

        cached_data_json = (
            '{"content": "Test content", "title": "Test Title", '
            '"cached_at": "2024-01-01T00:00:00", "content_hash": "abcd1234"}'
        )

        with patch(
            "src.infrastructure.cache.redis_cache.get_config",
            return_value=Mock(config=test_config),
        ), patch(
            "src.infrastructure.cache.redis_cache.redis.Redis", return_value=mock_redis
        ):
            cache = RedisDocumentCache()

            # Mock the Redis get method
            mock_redis.get = Mock(return_value=cached_data_json)

            result = cache.get_document_content("doc123")

            assert result == "Test content"
            mock_redis.get.assert_called_once_with("gdoc:content:doc123")

    def test_get_document_content_miss(self, mock_redis, test_config, reset_singletons):
        """Test cache miss for document content."""
        test_config.cache_config.enable = True
        test_config.cache_config.password = "test_password"

        with patch(
            "src.infrastructure.cache.redis_cache.get_config",
            return_value=Mock(config=test_config),
        ), patch(
            "src.infrastructure.cache.redis_cache.redis.Redis", return_value=mock_redis
        ):
            cache = RedisDocumentCache()

            # Mock the Redis get method to return None (cache miss)
            mock_redis.get = Mock(return_value=None)

            result = cache.get_document_content("doc123")

            assert result is None

    def test_get_document_title(self, mock_redis, test_config, reset_singletons):
        """Test retrieving document title from cache."""
        test_config.cache_config.enable = True
        test_config.cache_config.password = "test_password"

        cached_data_json = (
            '{"content": "Test content", "title": "Test Title", '
            '"cached_at": "2024-01-01T00:00:00", "content_hash": "abcd1234"}'
        )

        with patch(
            "src.infrastructure.cache.redis_cache.get_config",
            return_value=Mock(config=test_config),
        ), patch(
            "src.infrastructure.cache.redis_cache.redis.Redis", return_value=mock_redis
        ):
            cache = RedisDocumentCache()

            # Mock the Redis get method
            mock_redis.get = Mock(return_value=cached_data_json)

            result = cache.get_document_title("doc123")

            assert result == "Test Title"

    def test_invalidate_document_success(
        self, mock_redis, test_config, reset_singletons
    ):
        """Test successful document invalidation."""
        test_config.cache_config.enable = True
        test_config.cache_config.password = "test_password"

        with patch(
            "src.infrastructure.cache.redis_cache.get_config",
            return_value=Mock(config=test_config),
        ), patch(
            "src.infrastructure.cache.redis_cache.redis.Redis", return_value=mock_redis
        ):
            cache = RedisDocumentCache()

            # Mock the Redis delete method to return 1 (successful deletion)
            mock_redis.delete = Mock(return_value=1)

            result = cache.invalidate_document("doc123")

            assert result is True
            mock_redis.delete.assert_called_once_with("gdoc:content:doc123")

    def test_invalidate_document_not_found(
        self, mock_redis, test_config, reset_singletons
    ):
        """Test document invalidation when document not in cache."""
        test_config.cache_config.enable = True
        test_config.cache_config.password = "test_password"

        with patch(
            "src.infrastructure.cache.redis_cache.get_config",
            return_value=Mock(config=test_config),
        ), patch(
            "src.infrastructure.cache.redis_cache.redis.Redis", return_value=mock_redis
        ):
            cache = RedisDocumentCache()

            # Mock the Redis delete method to return 0 (no keys deleted)
            mock_redis.delete = Mock(return_value=0)

            result = cache.invalidate_document("doc123")

            assert result is False

    def test_get_cache_stats(self, mock_redis, test_config, reset_singletons):
        """Test cache statistics retrieval."""
        test_config.cache_config.enable = True
        test_config.cache_config.password = "test_password"

        with patch(
            "src.infrastructure.cache.redis_cache.get_config",
            return_value=Mock(config=test_config),
        ), patch(
            "src.infrastructure.cache.redis_cache.redis.Redis", return_value=mock_redis
        ):
            cache = RedisDocumentCache()

            # Mock the Redis info and keys methods
            mock_redis.info = Mock(
                return_value={"used_memory_human": "1.5M", "connected_clients": 5}
            )
            mock_redis.keys = Mock(
                return_value=["gdoc:content:doc1", "gdoc:content:doc2"]
            )

            stats = cache.get_cache_stats()

            assert stats["enabled"] is True
            assert stats["total_cached_documents"] == 2
            assert stats["redis_memory_used"] == "1.5M"
            assert stats["redis_connected_clients"] == 5
            assert stats["ttl_hours"] == 1

    def test_clear_all_documents(self, mock_redis, test_config, reset_singletons):
        """Test clearing all cached documents."""
        test_config.cache_config.enable = True
        test_config.cache_config.password = "test_password"

        with patch(
            "src.infrastructure.cache.redis_cache.get_config",
            return_value=Mock(config=test_config),
        ), patch(
            "src.infrastructure.cache.redis_cache.redis.Redis", return_value=mock_redis
        ):
            cache = RedisDocumentCache()

            # Mock the Redis keys and delete methods
            mock_redis.keys = Mock(
                return_value=["gdoc:content:doc1", "gdoc:content:doc2"]
            )
            mock_redis.delete = Mock(return_value=2)

            result = cache.clear_all_documents()

            assert result is True
            mock_redis.delete.assert_called_once_with(
                "gdoc:content:doc1", "gdoc:content:doc2"
            )

    def test_redis_error_handling(self, mock_redis, test_config, reset_singletons):
        """Test Redis error handling."""
        test_config.cache_config.enable = True
        test_config.cache_config.password = "test_password"

        with patch(
            "src.infrastructure.cache.redis_cache.get_config",
            return_value=Mock(config=test_config),
        ), patch(
            "src.infrastructure.cache.redis_cache.redis.Redis", return_value=mock_redis
        ):
            cache = RedisDocumentCache()

            # Mock the Redis get method to raise an exception
            mock_redis.get = Mock(side_effect=RedisError("Redis error"))

            result = cache.get_document_content("doc123")

            assert result is None

    def test_cache_key_generation(self, mock_redis, test_config):
        """Test cache key generation."""
        test_config.cache_config.enable = True
        test_config.cache_config.password = "test_password"

        with patch(
            "src.infrastructure.cache.redis_cache.get_config",
            return_value=Mock(config=test_config),
        ):
            cache = RedisDocumentCache()

            key = cache._generate_cache_key("doc123", "content")
            assert key == "gdoc:content:doc123"

            key = cache._generate_cache_key("doc456", "metadata")
            assert key == "gdoc:metadata:doc456"

    def test_serialize_deserialize_data(self, mock_redis, test_config):
        """Test data serialization and deserialization."""
        test_config.cache_config.enable = True
        test_config.cache_config.password = "test_password"

        with patch(
            "src.infrastructure.cache.redis_cache.get_config",
            return_value=Mock(config=test_config),
        ):
            cache = RedisDocumentCache()

            # Test serialization
            serialized = cache._serialize_document_data("Test content", "Test Title")
            assert isinstance(serialized, str)

            # Test deserialization
            deserialized = cache._deserialize_document_data(serialized)
            assert deserialized["content"] == "Test content"
            assert deserialized["title"] == "Test Title"
            assert "cached_at" in deserialized
            assert "content_hash" in deserialized


@pytest.mark.unit
def test_get_document_cache_function():
    """Test get_document_cache helper function."""
    cache1 = get_document_cache()
    cache2 = get_document_cache()

    assert cache1 is cache2
    assert isinstance(cache1, RedisDocumentCache)
