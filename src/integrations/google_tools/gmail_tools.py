"""Gmail tools specs with proper validation"""

import base64
from email.message import EmailMessage
from typing import List, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from llama_index.core.schema import Document
from llama_index.core.tools.tool_spec.base import BaseToolSpec

from src.infrastructure.logging.logging_config import get_logger
from src.integrations.google_tools.auth_utils import authenticate

logger = get_logger("google_tools.gmail")


class GmailToolSpec(BaseToolSpec):
    """Gmail tools spec with proper input validation"""

    spec_functions = [
        "search_messages",
        "create_draft",
        "update_draft",
        "get_draft",
        "send_draft",
    ]

    def __init__(self):
        logger.info("Initializing Gmail tool spec")
        try:
            self.service = build("gmail", "v1", credentials=authenticate())
            logger.debug("Gmail service initialized successfully")
        except HttpError as error:
            logger.error(f"Failed to initialize Gmail service: {error}")
            raise

    def search_messages(
        self, query: str, max_results: Optional[int] = None
    ) -> List[Document]:
        """
        Searches email messages given a query string and maximum number of results.

        Args:
            query (str): The search query (e.g., "from:user@example.com subject:test")
            max_results (Optional[int]): Maximum number of results to return

        Returns:
            List[Document]: List of email documents with metadata
        """
        logger.info(f"Searching emails with query: {query}")
        try:
            # pylint: disable=no-member
            results = (
                self.service.users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )

            messages = results.get("messages", [])
            logger.info(f"Found {len(messages)} messages")

            documents = []
            for msg in messages:
                msg_data = (
                    self.service.users()
                    .messages()
                    .get(userId="me", id=msg["id"], format="full")
                    .execute()
                )

                # Extract basic metadata
                headers = msg_data.get("payload", {}).get("headers", [])
                subject = next(
                    (h["value"] for h in headers if h["name"] == "Subject"), ""
                )
                sender = next((h["value"] for h in headers if h["name"] == "From"), "")

                # Get message body
                body = self._get_message_body(msg_data.get("payload", {}))

                documents.append(
                    Document(
                        text=body,
                        metadata={
                            "id": msg["id"],
                            "threadId": msg.get("threadId", ""),
                            "subject": subject,
                            "from": sender,
                            "snippet": msg_data.get("snippet", ""),
                        },
                    )
                )

            return documents

        except HttpError as error:
            logger.error(f"Failed to search messages: {error}")
            raise

    def _get_message_body(self, payload: dict) -> str:
        """Extract message body from payload"""
        if "parts" in payload:
            parts = payload["parts"]
            data = parts[0]["body"].get("data", "")
        else:
            data = payload.get("body", {}).get("data", "")

        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8")
        return ""

    def create_draft(
        self,
        to: Optional[List[str]] = None,
        subject: Optional[str] = None,
        message: Optional[str] = None,
    ) -> str:
        """
        Create a draft email with proper validation.

        Args:
            to (Optional[List[str]]): List of recipient email addresses (can be empty)
            subject (Optional[str]): Email subject
            message (Optional[str]): Email body content

        Returns:
            str: JSON string with draft ID and metadata
        """
        logger.info(f"Creating draft email to: {to}")

        try:
            draft_body = self._build_draft(to, subject, message)

            # pylint: disable=no-member
            draft = (
                self.service.users()
                .drafts()
                .create(userId="me", body=draft_body)
                .execute()
            )

            draft_id = draft.get("id")
            logger.info(f"Successfully created draft with ID: {draft_id}")
            return str(draft)

        except HttpError as error:
            logger.error(f"Failed to create draft: {error}")
            raise

    def _build_draft(
        self,
        to: Optional[List[str]] = None,
        subject: Optional[str] = None,
        message: Optional[str] = None,
    ) -> dict:
        """
        Build draft message with proper email formatting.

        Args:
            to (Optional[List[str]]): List of recipient email addresses
            subject (Optional[str]): Email subject
            message (Optional[str]): Email body

        Returns:
            dict: Draft body for Gmail API
        """
        email_message = EmailMessage()

        email_message.set_content(message or "")

        # Only set To header if we have recipients
        # This handles: None, [], and lists with emails
        if to:
            email_message["To"] = ", ".join(to)

        email_message["Subject"] = subject or ""

        encoded_message = base64.urlsafe_b64encode(email_message.as_bytes()).decode()

        return {"message": {"raw": encoded_message}}

    def update_draft(
        self,
        draft_id: str,
        to: Optional[List[str]] = None,
        subject: Optional[str] = None,
        message: Optional[str] = None,
    ) -> str:
        """
        Update an existing draft email.

        Args:
            draft_id (str): The ID of the draft to update (required)
            to (Optional[List[str]]): Updated recipient list
            subject (Optional[str]): Updated subject
            message (Optional[str]): Updated message body

        Returns:
            str: JSON string with updated draft metadata

        Raises:
            ValueError: If draft_id is None or empty
        """
        logger.info(f"Updating draft: {draft_id}")

        if not draft_id:
            error_msg = "draft_id is required to update a draft"
            logger.error(error_msg)
            raise ValueError(error_msg)

        try:
            # Get current draft to preserve existing values if not provided
            current_draft = self.get_draft(draft_id)

            # Use provided values or keep existing ones
            if to is None:
                # Extract current recipients
                headers = current_draft["message"]["payload"]["headers"]
                to_header = next((h["value"] for h in headers if h["name"] == "To"), "")
                if to_header:
                    to = [
                        email.strip() for email in to_header.split(",") if email.strip()
                    ]
                else:
                    to = []

            draft_body = self._build_draft(to, subject, message)

            # pylint: disable=no-member
            updated_draft = (
                self.service.users()
                .drafts()
                .update(userId="me", id=draft_id, body=draft_body)
                .execute()
            )

            logger.info(f"Successfully updated draft: {draft_id}")
            return str(updated_draft)

        except HttpError as error:
            logger.error(f"Failed to update draft {draft_id}: {error}")
            raise

    def get_draft(self, draft_id: str) -> dict:
        """
        Retrieve a draft email by ID.

        Args:
            draft_id (str): The ID of the draft to retrieve

        Returns:
            dict: Draft data including message content and metadata

        Raises:
            ValueError: If draft_id is None or empty
        """
        logger.info(f"Retrieving draft: {draft_id}")

        if not draft_id:
            error_msg = "draft_id is required to retrieve a draft"
            logger.error(error_msg)
            raise ValueError(error_msg)

        try:
            # pylint: disable=no-member
            draft = (
                self.service.users()
                .drafts()
                .get(userId="me", id=draft_id, format="full")
                .execute()
            )

            logger.info(f"Successfully retrieved draft: {draft_id}")
            return draft

        except HttpError as error:
            logger.error(f"Failed to retrieve draft {draft_id}: {error}")
            raise

    def send_draft(self, draft_id: str) -> str:
        """
        Send a draft email.

        Args:
            draft_id (str): The ID of the draft to send

        Returns:
            str: JSON string with sent message metadata

        Raises:
            ValueError: If draft_id is None or empty
        """
        logger.info(f"Sending draft: {draft_id}")

        if not draft_id:
            error_msg = "draft_id is required to send a draft"
            logger.error(error_msg)
            raise ValueError(error_msg)

        try:
            # pylint: disable=no-member
            sent_message = (
                self.service.users()
                .drafts()
                .send(userId="me", body={"id": draft_id})
                .execute()
            )

            message_id = sent_message.get("id")
            logger.info(f"Successfully sent draft {draft_id}, message ID: {message_id}")
            return str(sent_message)

        except HttpError as error:
            logger.error(f"Failed to send draft {draft_id}: {error}")
            raise
