"""Tests for Google authentication utilities."""

from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.integrations.google_tools.auth_utils import authenticate


class TestAuthenticate:
    """Test the authenticate function."""

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data='{"token": "test"}')
    @patch("src.integrations.google_tools.auth_utils.Credentials")
    def test_authenticate_with_existing_valid_token(
        self, mock_credentials, mock_file, mock_exists
    ):
        """Test authentication with existing valid token."""
        mock_exists.return_value = True
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_credentials.from_authorized_user_file.return_value = mock_creds

        result = authenticate()

        assert result == mock_creds
        mock_credentials.from_authorized_user_file.assert_called_once()

    @patch("os.path.exists")
    def test_authenticate_missing_credentials_file(self, mock_exists):
        """Test authentication fails when credentials.json is missing."""
        mock_exists.return_value = False

        with pytest.raises(FileNotFoundError, match="credentials.json is required"):
            authenticate()

    @patch("os.path.exists")
    @patch.dict("os.environ", {"RUNNING_IN_CONTAINER": "true"})
    def test_authenticate_container_mode_missing_token(self, mock_exists):
        """Test authentication fails in container mode when token.json is missing."""
        # credentials.json exists but token.json doesn't
        mock_exists.side_effect = lambda path: path == "credentials.json"

        with pytest.raises(
            FileNotFoundError,
            match="token.json is required when running in a container",
        ):
            authenticate()

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data='{"token": "test"}')
    @patch("src.integrations.google_tools.auth_utils.Credentials")
    @patch("src.integrations.google_tools.auth_utils.Request")
    def test_authenticate_refreshes_expired_token(
        self, mock_request, mock_credentials, mock_file, mock_exists
    ):
        """Test authentication refreshes expired token."""
        mock_exists.return_value = True
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_token"
        mock_credentials.from_authorized_user_file.return_value = mock_creds

        # After refresh, make it valid
        def refresh_side_effect(request):
            mock_creds.valid = True

        mock_creds.refresh.side_effect = refresh_side_effect

        result = authenticate()

        assert result == mock_creds
        mock_creds.refresh.assert_called_once()
