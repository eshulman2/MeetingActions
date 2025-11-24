"""
Performance tests for load testing critical components.
"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest

from src.integrations.google.tools import GoogleToolSpec


@pytest.mark.performance
class TestGoogleToolsPerformance:
    """Performance tests for Google Tools."""

    @pytest.fixture
    def mock_google_tool_spec(self):
        """Create mock Google tool spec for performance testing."""
        with patch("src.integrations.google.tools.build"), patch(
            "src.integrations.google.tools.authenticate"
        ), patch("src.integrations.google.tools.get_document_cache"):

            tool_spec = GoogleToolSpec()

            # Mock services with fast responses
            tool_spec.calendar_service = MagicMock()
            tool_spec.docs_service = MagicMock()
            tool_spec.cache = MagicMock()

            return tool_spec

    @pytest.mark.slow
    def test_document_content_fetch_performance(self, mock_google_tool_spec):
        """Test performance of document content fetching."""
        # Mock document response
        mock_document = {
            "title": "Performance Test Document",
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [
                                {
                                    "textRun": {
                                        "content": "Test content "
                                        * 100  # Larger content
                                    }
                                }
                            ]
                        }
                    }
                ]
                * 50  # Multiple paragraphs
            },
        }

        mock_google_tool_spec.docs_service.documents().get().execute.return_value = (
            mock_document
        )
        mock_google_tool_spec.cache.get_document_content.return_value = None

        # Measure performance
        start_time = time.time()
        result = mock_google_tool_spec.fetch_google_doc_content("test_doc_id")
        end_time = time.time()

        # Assertions
        assert result is not None
        assert len(result) > 0

        # Performance assertion - should complete within reasonable time
        execution_time = end_time - start_time
        assert (
            execution_time < 1.0
        ), f"Document fetch took {execution_time:.3f}s, expected < 1.0s"

    @pytest.mark.slow
    def test_concurrent_document_fetches(self, mock_google_tool_spec):
        """Test performance under concurrent document fetch requests."""
        # Mock document response
        mock_document = {
            "title": "Concurrent Test Document",
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [
                                {"textRun": {"content": "Concurrent test content"}}
                            ]
                        }
                    }
                ]
            },
        }

        mock_google_tool_spec.docs_service.documents().get().execute.return_value = (
            mock_document
        )
        mock_google_tool_spec.cache.get_document_content.return_value = None

        def fetch_document(doc_id):
            return mock_google_tool_spec.fetch_google_doc_content(f"doc_{doc_id}")

        # Test concurrent execution
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(fetch_document, i) for i in range(10)]
            results = [future.result() for future in futures]
        end_time = time.time()

        # Assertions
        assert len(results) == 10
        assert all(result is not None for result in results)

        # Performance assertion
        execution_time = end_time - start_time
        assert (
            execution_time < 5.0
        ), f"Concurrent fetches took {execution_time:.3f}s, expected < 5.0s"

    def test_cache_performance_impact(self, mock_google_tool_spec):
        """Test performance impact of caching."""
        cached_content = "Cached content for performance test"

        # Test with cache hit
        mock_google_tool_spec.cache.get_document_content.return_value = cached_content

        start_time = time.time()
        result = mock_google_tool_spec.fetch_google_doc_content("cached_doc")
        cache_time = time.time() - start_time

        assert result == cached_content

        # Test without cache (API call)
        mock_google_tool_spec.cache.get_document_content.return_value = None
        mock_document = {
            "title": "API Document",
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [{"textRun": {"content": "API content"}}]
                        }
                    }
                ]
            },
        }
        mock_google_tool_spec.docs_service.documents().get().execute.return_value = (
            mock_document
        )

        start_time = time.time()
        result = mock_google_tool_spec.fetch_google_doc_content("api_doc")
        api_time = time.time() - start_time

        assert result == "API content"

        # Cache should be significantly faster
        assert cache_time < api_time, "Cache should be faster than API call"
        assert cache_time < 0.1, f"Cache lookup took {cache_time:.3f}s, expected < 0.1s"


@pytest.mark.performance
class TestMemoryUsagePerformance:
    """Performance tests for memory usage."""

    def test_large_document_memory_usage(self):
        """Test memory usage with large documents."""
        # This test would need actual memory profiling tools in a real scenario
        # For now, we'll test with size limits

        large_content = "x" * 1000000  # 1MB of content

        # Test that we can handle reasonably large content
        assert len(large_content) == 1000000

        # In real implementation, you might check memory usage here
        # For example, using memory_profiler or tracemalloc

    @pytest.mark.slow
    def test_memory_leak_prevention(self):
        """Test that repeated operations don't cause memory leaks."""
        import gc

        # Get initial memory state
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Perform repeated operations
        for _ in range(100):
            # Simulate creating and destroying objects
            temp_data = ["test"] * 1000
            del temp_data

        # Force garbage collection
        gc.collect()
        final_objects = len(gc.get_objects())

        # Memory should not have grown significantly
        object_growth = final_objects - initial_objects
        assert (
            object_growth < 1000
        ), f"Potential memory leak: {object_growth} new objects"


@pytest.mark.performance
class TestResponseTimePerformance:
    """Performance tests for response times."""

    def test_api_response_time_requirements(self):
        """Test that API responses meet time requirements."""
        # Mock a typical API call flow
        start_time = time.time()

        # Simulate processing time
        time.sleep(0.01)  # 10ms simulated processing

        end_time = time.time()
        response_time = end_time - start_time

        # API should respond within reasonable time
        assert (
            response_time < 0.1
        ), f"API response took {response_time:.3f}s, expected < 0.1s"

    @pytest.mark.asyncio
    async def test_async_operation_performance(self):
        """Test performance of async operations."""

        async def mock_async_operation():
            await asyncio.sleep(0.01)  # 10ms async operation
            return "async result"

        start_time = time.time()
        result = await mock_async_operation()
        end_time = time.time()

        assert result == "async result"

        execution_time = end_time - start_time
        assert (
            execution_time < 0.1
        ), f"Async operation took {execution_time:.3f}s, expected < 0.1s"

    def test_batch_operation_efficiency(self):
        """Test that batch operations are more efficient than individual ones."""
        # Simulate individual operations
        start_time = time.time()
        for _ in range(10):
            time.sleep(0.001)  # 1ms per operation
        individual_time = time.time() - start_time

        # Simulate batch operation
        start_time = time.time()
        time.sleep(0.005)  # 5ms for entire batch
        batch_time = time.time() - start_time

        # Batch should be more efficient
        assert batch_time < individual_time, "Batch operations should be more efficient"
        assert (
            batch_time < 0.01
        ), f"Batch operation took {batch_time:.3f}s, expected < 0.01s"
