"""
Tests for Google Tools integration.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from googleapiclient.errors import HttpError

from src.integrations.google_tools.google_tools import GoogleToolSpec


@pytest.fixture
def mock_cache():
    """Mock Redis cache."""
    cache = MagicMock()
    cache.get_document_title.return_value = None
    cache.get_document_content.return_value = None
    return cache


@pytest.fixture
def mock_services():
    """Mock Google API services."""
    calendar_service = MagicMock()
    meet_service = MagicMock()
    docs_service = MagicMock()
    return calendar_service, meet_service, docs_service


@pytest.fixture
def google_tool_spec(mock_cache, mock_services):
    """Create GoogleToolSpec instance with mocked dependencies."""
    calendar_service, meet_service, docs_service = mock_services

    with patch("src.integrations.google_tools.google_tools.build") as mock_build, patch(
        "src.integrations.google_tools.google_tools.authenticate"
    ), patch("src.integrations.google_tools.google_tools.get_cache") as mock_get_cache:

        mock_build.side_effect = [calendar_service, meet_service, docs_service]
        mock_get_cache.return_value = mock_cache

        tool_spec = GoogleToolSpec()
        tool_spec.calendar_service = calendar_service
        tool_spec.meet_service = meet_service
        tool_spec.docs_service = docs_service
        tool_spec.cache = mock_cache

        return tool_spec


class TestGoogleToolSpec:
    """Test cases for GoogleToolSpec."""

    def test_initialization(self, google_tool_spec):
        """Test GoogleToolSpec initialization."""
        assert hasattr(google_tool_spec, "calendar_service")
        assert hasattr(google_tool_spec, "meet_service")
        assert hasattr(google_tool_spec, "docs_service")
        assert hasattr(google_tool_spec, "cache")

    def test_spec_functions_defined(self):
        """Test that all spec functions are properly defined."""
        expected_functions = [
            "get_event_gdoc_attachments_ids",
            "get_events_by_date",
            "create_event",
            "get_google_doc_title",
            "fetch_google_doc_content",
        ]
        assert GoogleToolSpec.spec_functions == expected_functions

    def test_get_event_gdoc_attachments_ids_success(self, google_tool_spec):
        """Test successful retrieval of Google Doc attachments."""
        # Mock event with Google Doc attachments
        mock_event = {
            "attachments": [
                {
                    "mimeType": "application/vnd.google-apps.document",
                    "fileId": "doc1_id",
                },
                {"mimeType": "application/pdf", "fileId": "pdf_id"},
                {
                    "mimeType": "application/vnd.google-apps.document",
                    "fileId": "doc2_id",
                },
            ]
        }

        # Set up the mock properly to avoid extra calls
        mock_get = google_tool_spec.calendar_service.events().get
        mock_get.return_value.execute.return_value = mock_event

        result = google_tool_spec.get_event_gdoc_attachments_ids("event123")

        assert result == ["doc1_id", "doc2_id"]
        mock_get.assert_called_once_with(calendarId="primary", eventId="event123")

    def test_get_event_gdoc_attachments_ids_no_attachments(self, google_tool_spec):
        """Test handling of events with no attachments."""
        mock_event = {}
        google_tool_spec.calendar_service.events().get().execute.return_value = (
            mock_event
        )

        result = google_tool_spec.get_event_gdoc_attachments_ids("event123")

        assert result == "Event has no attachments."

    def test_get_event_gdoc_attachments_ids_http_error(self, google_tool_spec):
        """Test error handling for HTTP errors."""
        # Set up the mock properly to avoid extra calls
        mock_get = google_tool_spec.calendar_service.events().get

        # Create a proper HttpError with required arguments
        mock_resp = Mock()
        mock_resp.status = 404
        mock_resp.reason = "Not Found"
        http_error = HttpError(
            resp=mock_resp, content=b'{"error": {"message": "Not found"}}'
        )

        mock_get.return_value.execute.side_effect = http_error

        with pytest.raises(HttpError):
            google_tool_spec.get_event_gdoc_attachments_ids("event123")

    def test_get_events_by_date_success(self, google_tool_spec):
        """Test successful retrieval of events by date."""
        mock_events = {
            "items": [
                {"summary": "Event 1", "id": "event1"},
                {"summary": "Event 2", "id": "event2"},
            ]
        }

        google_tool_spec.calendar_service.events().list().execute.return_value = (
            mock_events
        )

        result = google_tool_spec.get_events_by_date(2024, 1, 15)

        assert len(result) == 2
        assert result[0]["summary"] == "Event 1"
        assert result[1]["summary"] == "Event 2"

        # Verify the API call
        call_args = google_tool_spec.calendar_service.events().list.call_args[1]
        assert call_args["calendarId"] == "primary"
        assert call_args["singleEvents"] is True
        assert call_args["orderBy"] == "startTime"

    def test_get_events_by_date_no_events(self, google_tool_spec):
        """Test handling when no events are found."""
        mock_events = {"items": []}
        google_tool_spec.calendar_service.events().list().execute.return_value = (
            mock_events
        )

        result = google_tool_spec.get_events_by_date(2024, 1, 15)

        assert result == []

    def test_create_event_success(self, google_tool_spec):
        """Test successful event creation."""
        mock_created_event = {"id": "created_event_id", "summary": "Test Event"}

        google_tool_spec.calendar_service.events().insert().execute.return_value = (
            mock_created_event
        )

        result = google_tool_spec.create_event(
            start_time="2024-01-15T10:00:00-08:00",
            end_time="2024-01-15T11:00:00-08:00",
            summary="Test Event",
            location="Test Location",
            description="Test Description",
            attendees=["test@example.com"],
        )

        assert result["id"] == "created_event_id"
        assert result["summary"] == "Test Event"

        # Verify the API call
        call_args = google_tool_spec.calendar_service.events().insert.call_args[1]
        assert call_args["calendarId"] == "primary"
        event_body = call_args["body"]
        assert event_body["summary"] == "Test Event"
        assert event_body["location"] == "Test Location"
        assert event_body["description"] == "Test Description"
        assert event_body["attendees"] == [{"email": "test@example.com"}]

    def test_create_event_no_attendees(self, google_tool_spec):
        """Test event creation without attendees."""
        mock_created_event = {"id": "created_event_id"}
        google_tool_spec.calendar_service.events().insert().execute.return_value = (
            mock_created_event
        )

        google_tool_spec.create_event(
            start_time="2024-01-15T10:00:00-08:00",
            end_time="2024-01-15T11:00:00-08:00",
            summary="Test Event",
        )

        call_args = google_tool_spec.calendar_service.events().insert.call_args[1]
        event_body = call_args["body"]
        assert event_body["attendees"] == []

    def test_get_google_doc_title_from_cache(self, google_tool_spec):
        """Test retrieving document title from cache."""
        google_tool_spec.cache.get_document_title.return_value = "Cached Title"

        result = google_tool_spec.get_google_doc_title("doc123")

        assert result == "Cached Title"
        google_tool_spec.cache.get_document_title.assert_called_once_with("doc123")
        google_tool_spec.docs_service.documents().get.assert_not_called()

    def test_get_google_doc_title_from_api(self, google_tool_spec):
        """Test retrieving document title from API."""
        google_tool_spec.cache.get_document_title.return_value = None
        mock_document = {"title": "API Title"}

        # Set up the mock properly to avoid extra calls
        mock_get = google_tool_spec.docs_service.documents().get
        mock_get.return_value.execute.return_value = mock_document

        result = google_tool_spec.get_google_doc_title("doc123")

        assert result == "API Title"
        mock_get.assert_called_once_with(documentId="doc123", fields="title")

    def test_get_google_doc_title_not_found(self, google_tool_spec):
        """Test handling when document is not found."""
        google_tool_spec.cache.get_document_title.return_value = None
        google_tool_spec.docs_service.documents().get().execute.side_effect = HttpError(
            resp=Mock(status=404), content=b"Not found"
        )

        result = google_tool_spec.get_google_doc_title("doc123")

        assert "not found" in result.lower()

    @patch("src.integrations.google_tools.google_tools.get_config")
    def test_fetch_google_doc_content_from_cache(
        self, mock_get_config, google_tool_spec
    ):
        """Test retrieving document content from cache."""
        google_tool_spec.cache.get_document_content.return_value = "Cached content"

        result = google_tool_spec.fetch_google_doc_content("doc123")

        assert result == "Cached content"
        google_tool_spec.docs_service.documents().get.assert_not_called()

    @patch("src.integrations.google_tools.google_tools.get_config")
    def test_fetch_google_doc_content_from_api(self, mock_get_config, google_tool_spec):
        """Test retrieving document content from API."""
        # Mock config
        mock_config = MagicMock()
        mock_config.config.max_document_length = 10000
        mock_get_config.return_value = mock_config

        google_tool_spec.cache.get_document_content.return_value = None

        mock_document = {
            "title": "Test Document",
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [{"textRun": {"content": "Test content"}}]
                        }
                    }
                ]
            },
        }

        google_tool_spec.docs_service.documents().get().execute.return_value = (
            mock_document
        )

        result = google_tool_spec.fetch_google_doc_content("doc123")

        assert result == "Test content"
        google_tool_spec.cache.set_document_content.assert_called_once_with(
            "doc123", "Test content", "Test Document"
        )

    @patch("src.integrations.google_tools.google_tools.get_config")
    def test_fetch_google_doc_content_exceeds_length(
        self, mock_get_config, google_tool_spec
    ):
        """Test handling when document content exceeds maximum length."""
        # Mock config with small max length
        mock_config = MagicMock()
        mock_config.config.max_document_length = 5
        mock_get_config.return_value = mock_config

        google_tool_spec.cache.get_document_content.return_value = None

        mock_document = {
            "title": "Test Document",
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [
                                {
                                    "textRun": {
                                        "content": (
                                            "This is a very long content "
                                            "that exceeds the limit"
                                        )
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        }

        google_tool_spec.docs_service.documents().get().execute.return_value = (
            mock_document
        )

        result = google_tool_spec.fetch_google_doc_content("doc123")

        assert "exceeds maximum length" in result

    def test_read_paragraph_element_with_text_run(self, google_tool_spec):
        """Test reading paragraph element with text run."""
        element = {"textRun": {"content": "Test text content"}}

        result = google_tool_spec.read_paragraph_element(element)
        assert result == "Test text content"

    def test_read_paragraph_element_without_text_run(self, google_tool_spec):
        """Test reading paragraph element without text run."""
        element = {}

        result = google_tool_spec.read_paragraph_element(element)
        assert result == ""

    def test_read_structural_elements_paragraph(self, google_tool_spec):
        """Test reading structural elements with paragraph."""
        elements = [
            {
                "paragraph": {
                    "elements": [
                        {"textRun": {"content": "First paragraph. "}},
                        {"textRun": {"content": "Same paragraph continues."}},
                    ]
                }
            }
        ]

        result = google_tool_spec.read_structural_elements(elements)
        assert result == "First paragraph. Same paragraph continues."

    def test_read_structural_elements_table(self, google_tool_spec):
        """Test reading structural elements with table."""
        elements = [
            {
                "table": {
                    "tableRows": [
                        {
                            "tableCells": [
                                {
                                    "content": [
                                        {
                                            "paragraph": {
                                                "elements": [
                                                    {"textRun": {"content": "Cell 1"}}
                                                ]
                                            }
                                        }
                                    ]
                                },
                                {
                                    "content": [
                                        {
                                            "paragraph": {
                                                "elements": [
                                                    {"textRun": {"content": "Cell 2"}}
                                                ]
                                            }
                                        }
                                    ]
                                },
                            ]
                        }
                    ]
                }
            }
        ]

        result = google_tool_spec.read_structural_elements(elements)
        assert result == "Cell 1Cell 2"
