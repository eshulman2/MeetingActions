"""
Tests for Gmail Tools integration.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from googleapiclient.errors import HttpError

from src.integrations.google_tools.gmail_tools import GmailToolSpec


@pytest.fixture
def mock_gmail_service():
    """Mock Gmail API service."""
    return MagicMock()


@pytest.fixture
def gmail_tool_spec(mock_gmail_service):
    """Create GmailToolSpec instance with mocked dependencies."""
    with patch("src.integrations.google_tools.gmail_tools.build") as mock_build, patch(
        "src.integrations.google_tools.gmail_tools.authenticate"
    ):
        mock_build.return_value = mock_gmail_service

        tool_spec = GmailToolSpec()
        tool_spec.service = mock_gmail_service

        return tool_spec


class TestGmailToolSpec:
    """Test cases for GmailToolSpec."""

    def test_initialization(self, gmail_tool_spec):
        """Test GmailToolSpec initialization."""
        assert hasattr(gmail_tool_spec, "service")

    def test_spec_functions_defined(self):
        """Test that all spec functions are properly defined."""
        expected_functions = [
            "search_messages",
            "create_draft",
            "update_draft",
            "get_draft",
            "send_draft",
        ]
        assert GmailToolSpec.spec_functions == expected_functions

    def test_search_messages_success(self, gmail_tool_spec):
        """Test successful email search."""
        mock_messages = {
            "messages": [
                {"id": "msg1", "threadId": "thread1"},
                {"id": "msg2", "threadId": "thread2"},
            ]
        }

        mock_msg_data = {
            "id": "msg1",
            "threadId": "thread1",
            "snippet": "Test snippet",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "From", "value": "sender@example.com"},
                ],
                "body": {"data": "VGVzdCBib2R5"},  # base64 encoded "Test body"
            },
        }

        # Setup mocks
        gmail_tool_spec.service.users().messages().list().execute.return_value = (
            mock_messages
        )
        gmail_tool_spec.service.users().messages().get().execute.return_value = (
            mock_msg_data
        )

        result = gmail_tool_spec.search_messages("from:sender@example.com")

        assert len(result) == 2
        assert result[0].metadata["id"] == "msg1"
        assert result[0].metadata["subject"] == "Test Subject"
        assert result[0].metadata["from"] == "sender@example.com"

    def test_search_messages_no_results(self, gmail_tool_spec):
        """Test search with no results."""
        mock_messages = {"messages": []}
        gmail_tool_spec.service.users().messages().list().execute.return_value = (
            mock_messages
        )

        result = gmail_tool_spec.search_messages("from:nonexistent@example.com")

        assert result == []

    def test_search_messages_with_max_results(self, gmail_tool_spec):
        """Test search with max_results parameter."""
        mock_messages = {"messages": []}
        gmail_tool_spec.service.users().messages().list().execute.return_value = (
            mock_messages
        )

        gmail_tool_spec.search_messages("test", max_results=10)

        # Verify maxResults was passed to the API
        call_args = gmail_tool_spec.service.users().messages().list.call_args[1]
        assert call_args["maxResults"] == 10

    def test_search_messages_http_error(self, gmail_tool_spec):
        """Test error handling for HTTP errors."""
        mock_resp = Mock()
        mock_resp.status = 500
        mock_resp.reason = "Internal Server Error"
        http_error = HttpError(
            resp=mock_resp, content=b'{"error": {"message": "Server error"}}'
        )

        gmail_tool_spec.service.users().messages().list().execute.side_effect = (
            http_error
        )

        with pytest.raises(HttpError):
            gmail_tool_spec.search_messages("test query")

    def test_create_draft_success(self, gmail_tool_spec):
        """Test successful draft creation."""
        mock_draft = {"id": "draft123", "message": {"id": "msg123"}}
        gmail_tool_spec.service.users().drafts().create().execute.return_value = (
            mock_draft
        )

        result = gmail_tool_spec.create_draft(
            to=["recipient@example.com"],
            subject="Test Subject",
            message="Test message body",
        )

        assert "draft123" in result
        call_args = gmail_tool_spec.service.users().drafts().create.call_args[1]
        assert call_args["userId"] == "me"
        assert "body" in call_args

    def test_create_draft_empty_recipients(self, gmail_tool_spec):
        """Test creating draft with empty recipient list."""
        mock_draft = {"id": "draft123"}
        gmail_tool_spec.service.users().drafts().create().execute.return_value = (
            mock_draft
        )

        result = gmail_tool_spec.create_draft(
            to=[], subject="Test Subject", message="Test body"
        )

        assert "draft123" in result

    def test_create_draft_none_recipients(self, gmail_tool_spec):
        """Test creating draft with None recipients."""
        mock_draft = {"id": "draft123"}
        gmail_tool_spec.service.users().drafts().create().execute.return_value = (
            mock_draft
        )

        result = gmail_tool_spec.create_draft(
            to=None, subject="Test Subject", message="Test body"
        )

        assert "draft123" in result

    def test_create_draft_http_error(self, gmail_tool_spec):
        """Test error handling when creating draft."""
        mock_resp = Mock()
        mock_resp.status = 400
        mock_resp.reason = "Bad Request"
        http_error = HttpError(
            resp=mock_resp, content=b'{"error": {"message": "Invalid request"}}'
        )

        gmail_tool_spec.service.users().drafts().create().execute.side_effect = (
            http_error
        )

        with pytest.raises(HttpError):
            gmail_tool_spec.create_draft(
                to=["test@example.com"], subject="Test", message="Test"
            )

    def test_get_draft_success(self, gmail_tool_spec):
        """Test successful draft retrieval."""
        mock_draft = {
            "id": "draft123",
            "message": {
                "id": "msg123",
                "payload": {
                    "headers": [
                        {"name": "To", "value": "recipient@example.com"},
                        {"name": "Subject", "value": "Test Subject"},
                    ]
                },
            },
        }

        gmail_tool_spec.service.users().drafts().get().execute.return_value = mock_draft

        result = gmail_tool_spec.get_draft("draft123")

        assert result["id"] == "draft123"
        call_args = gmail_tool_spec.service.users().drafts().get.call_args[1]
        assert call_args["id"] == "draft123"
        assert call_args["format"] == "full"

    def test_get_draft_empty_id(self, gmail_tool_spec):
        """Test error when draft_id is empty."""
        with pytest.raises(ValueError, match="draft_id is required"):
            gmail_tool_spec.get_draft("")

    def test_get_draft_none_id(self, gmail_tool_spec):
        """Test error when draft_id is None."""
        with pytest.raises(ValueError, match="draft_id is required"):
            gmail_tool_spec.get_draft(None)

    def test_get_draft_http_error(self, gmail_tool_spec):
        """Test error handling when retrieving draft."""
        mock_resp = Mock()
        mock_resp.status = 404
        mock_resp.reason = "Not Found"
        http_error = HttpError(
            resp=mock_resp, content=b'{"error": {"message": "Draft not found"}}'
        )

        gmail_tool_spec.service.users().drafts().get().execute.side_effect = http_error

        with pytest.raises(HttpError):
            gmail_tool_spec.get_draft("nonexistent_draft")

    def test_update_draft_success(self, gmail_tool_spec):
        """Test successful draft update."""
        # Mock the current draft
        mock_current_draft = {
            "id": "draft123",
            "message": {
                "payload": {
                    "headers": [
                        {"name": "To", "value": "old@example.com"},
                        {"name": "Subject", "value": "Old Subject"},
                    ]
                }
            },
        }

        mock_updated_draft = {"id": "draft123", "message": {"id": "msg123"}}

        gmail_tool_spec.service.users().drafts().get().execute.return_value = (
            mock_current_draft
        )
        gmail_tool_spec.service.users().drafts().update().execute.return_value = (
            mock_updated_draft
        )

        result = gmail_tool_spec.update_draft(
            draft_id="draft123",
            to=["new@example.com"],
            subject="New Subject",
            message="New message",
        )

        assert "draft123" in result
        call_args = gmail_tool_spec.service.users().drafts().update.call_args[1]
        assert call_args["id"] == "draft123"

    def test_update_draft_preserve_recipients(self, gmail_tool_spec):
        """Test updating draft while preserving existing recipients."""
        mock_current_draft = {
            "id": "draft123",
            "message": {
                "payload": {
                    "headers": [
                        {"name": "To", "value": "existing@example.com"},
                        {"name": "Subject", "value": "Old Subject"},
                    ]
                }
            },
        }

        mock_updated_draft = {"id": "draft123"}
        gmail_tool_spec.service.users().drafts().get().execute.return_value = (
            mock_current_draft
        )
        gmail_tool_spec.service.users().drafts().update().execute.return_value = (
            mock_updated_draft
        )

        # Update only subject, not recipients
        gmail_tool_spec.update_draft(
            draft_id="draft123", to=None, subject="New Subject", message=None
        )

        # Verify get was called to fetch current state
        call_args = gmail_tool_spec.service.users().drafts().get.call_args[1]
        assert call_args["id"] == "draft123"
        assert call_args["format"] == "full"

    def test_update_draft_empty_id(self, gmail_tool_spec):
        """Test error when updating with empty draft_id."""
        with pytest.raises(ValueError, match="draft_id is required"):
            gmail_tool_spec.update_draft(draft_id="", subject="New Subject")

    def test_update_draft_none_id(self, gmail_tool_spec):
        """Test error when updating with None draft_id."""
        with pytest.raises(ValueError, match="draft_id is required"):
            gmail_tool_spec.update_draft(draft_id=None, subject="New Subject")

    def test_send_draft_success(self, gmail_tool_spec):
        """Test successful draft sending."""
        mock_sent = {"id": "msg123", "labelIds": ["SENT"]}
        gmail_tool_spec.service.users().drafts().send().execute.return_value = mock_sent

        result = gmail_tool_spec.send_draft("draft123")

        assert "msg123" in result
        call_args = gmail_tool_spec.service.users().drafts().send.call_args[1]
        assert call_args["userId"] == "me"
        assert call_args["body"]["id"] == "draft123"

    def test_send_draft_empty_id(self, gmail_tool_spec):
        """Test error when sending with empty draft_id."""
        with pytest.raises(ValueError, match="draft_id is required"):
            gmail_tool_spec.send_draft("")

    def test_send_draft_none_id(self, gmail_tool_spec):
        """Test error when sending with None draft_id."""
        with pytest.raises(ValueError, match="draft_id is required"):
            gmail_tool_spec.send_draft(None)

    def test_send_draft_http_error(self, gmail_tool_spec):
        """Test error handling when sending draft."""
        mock_resp = Mock()
        mock_resp.status = 400
        mock_resp.reason = "Bad Request"
        http_error = HttpError(
            resp=mock_resp,
            content=b'{"error": {"message": "Cannot send incomplete draft"}}',
        )

        gmail_tool_spec.service.users().drafts().send().execute.side_effect = http_error

        with pytest.raises(HttpError):
            gmail_tool_spec.send_draft("draft123")

    def test_get_message_body_from_parts(self, gmail_tool_spec):
        """Test extracting message body from parts."""
        payload = {"parts": [{"body": {"data": "VGVzdCBib2R5"}}]}  # "Test body"

        result = gmail_tool_spec._get_message_body(payload)

        assert result == "Test body"

    def test_get_message_body_from_direct_data(self, gmail_tool_spec):
        """Test extracting message body from direct data."""
        payload = {"body": {"data": "RGlyZWN0IGJvZHk="}}  # "Direct body"

        result = gmail_tool_spec._get_message_body(payload)

        assert result == "Direct body"

    def test_get_message_body_empty(self, gmail_tool_spec):
        """Test extracting empty message body."""
        payload = {}

        result = gmail_tool_spec._get_message_body(payload)

        assert result == ""

    def test_build_draft_with_all_fields(self, gmail_tool_spec):
        """Test building draft with all fields populated."""
        result = gmail_tool_spec._build_draft(
            to=["test1@example.com", "test2@example.com"],
            subject="Test Subject",
            message="Test Message",
        )

        assert "message" in result
        assert "raw" in result["message"]
        # Verify base64 encoded message exists
        assert len(result["message"]["raw"]) > 0

    def test_build_draft_with_none_values(self, gmail_tool_spec):
        """Test building draft with None values."""
        result = gmail_tool_spec._build_draft(to=None, subject=None, message=None)

        assert "message" in result
        assert "raw" in result["message"]

    def test_build_draft_with_empty_list(self, gmail_tool_spec):
        """Test building draft with empty recipient list."""
        result = gmail_tool_spec._build_draft(
            to=[], subject="Test", message="Test message"
        )

        assert "message" in result
        assert "raw" in result["message"]
