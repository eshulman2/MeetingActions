"""Google calendar tools specs"""

from datetime import datetime
from typing import Dict, List, Optional

import tzlocal
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from llama_index.core.tools.tool_spec.base import BaseToolSpec

from src.infrastructure.cache import get_document_cache
from src.infrastructure.config import get_config
from src.infrastructure.logging.logging_config import get_logger
from src.integrations.google_tools.auth_utils import authenticate

logger = get_logger("google_tools.calendar")


class GoogleToolSpec(BaseToolSpec):
    """Google calendar tools specs"""

    spec_functions = [
        "get_event_gdoc_attachments_ids",
        "get_events_by_date",
        "create_event",
        "get_google_doc_title",
        "fetch_google_doc_content",
    ]

    def __init__(self):
        logger.info("Initializing Google Calendar tool spec")
        try:
            logger.info("Initializing Google tools spec")

            self.calendar_service = build("calendar", "v3", credentials=authenticate())
            logger.debug("Google Calendar service initialized successfully")

            self.meet_service = build("meet", "v2", credentials=authenticate())
            logger.debug("Google Meet service initialized successfully")

            self.docs_service = build("docs", "v1", credentials=authenticate())
            logger.debug("Google Docs service initialized successfully")

            self.cache = get_document_cache()
            logger.debug("Redis cache initialized")

        except HttpError as error:
            logger.error(f"Failed to initialize Google Calendar service: {error}")
            raise HttpError from error

    def get_event_gdoc_attachments_ids(
        self, event_id: str, calendar_id: str = "primary"
    ) -> List[str] | str:
        """
        Retrieves an event from Google Calendar and extracts the file IDs of
        all attached Google Docs.

        Args:
            calendar_id (str): The ID of the calendar containing the event.
                            Usually 'primary' for the user's main calendar.
            event_id (str): The unique ID of the event.

        Returns:
            list: A list of strings, where each string is the file ID of a
                Google Doc attachment. Returns an empty list if no Google Docs
                are attached or if the event has no attachments.
        """
        logger.info(
            f"Getting Google Doc attachments for event: {event_id} "
            f"in calendar: {calendar_id}"
        )
        google_doc_ids = []
        google_doc_mime_type = "application/vnd.google-apps.document"
        try:
            # Call the Calendar API to get the specific event
            # pylint: disable=no-member
            event = (
                self.calendar_service.events()
                .get(calendarId=calendar_id, eventId=event_id)
                .execute()
            )
            logger.debug(f"Successfully retrieved event: {event_id}")

            # Check if the 'attachments' key exists in the event object
            if "attachments" in event:
                logger.debug(f"Found {len(event['attachments'])} attachments")
                for attachment in event["attachments"]:
                    # Check if the attachment is a Google Doc by its MIME type
                    if attachment.get("mimeType") == google_doc_mime_type:
                        file_id = attachment.get("fileId")
                        if file_id:
                            google_doc_ids.append(file_id)
                            logger.debug(f"Found Google Doc attachment: {file_id}")

            else:
                logger.info("Event has no attachments")
                return "Event has no attachments."

            logger.info(f"Found {len(google_doc_ids)} Google Doc attachments")
            return google_doc_ids

        except HttpError as error:
            logger.error(f"Failed to get event attachments for {event_id}: {error}")
            raise

    def get_events_by_date(
        self, year: int, month: int, day: int, calendar_id: str = "primary"
    ) -> List[Dict]:
        """
        Fetches all Google Calendar events for a specific date.

            year (int): The year of the target date.
            month (int): The month of the target date (1-12).
            day (int): The day of the target date (1-31).
            calendar_id (str, optional): The ID of the calendar to fetch
                                        events from. Defaults to 'primary'.

            list: A list of event dictionaries for the specified date, or None
                if an error occurs.

        Raises:
            googleapiclient.errors.HttpError: If the Google Calendar API
            request fails.
        """
        target_date = datetime(year, month, day).date()
        # Format the date to RFC3339 timestamp format required by the API.
        # 'Z' indicates UTC time.
        time_min = datetime.combine(target_date, datetime.min.time()).isoformat() + "Z"
        time_max = datetime.combine(target_date, datetime.max.time()).isoformat() + "Z"

        logger.info(
            f"Fetching events for {target_date.strftime('%Y-%m-%d')} "
            f"from calendar: {calendar_id}"
        )

        try:
            # Call the Calendar API
            # pylint: disable=no-member
            events_result = (
                self.calendar_service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = events_result.get("items", [])
            logger.info(
                f"Found {len(events)} events for {target_date.strftime('%Y-%m-%d')}"
            )
            return events

        except HttpError as error:
            logger.error(
                f"Failed to get events for {target_date.strftime('%Y-%m-%d')}: {error}"
            )
            raise HttpError from error

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def create_event(
        self,
        start_time: str,
        end_time: str,
        summary: Optional[str] = None,
        location: Optional[str] = None,
        description: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        recurrence: Optional[List[str]] = None,
    ) -> Dict:
        """
        Creates a new event in the user's primary Google Calendar.

        Args:
            summary (str): The title of the event.
            location (str): The location of the event.
            description (str): A description of the event.
            start_time (str): The start time of the event in RFC3339 format
                (e.g., "2025-08-28T09:00:00-07:00").
            end_time (str): The end time of the event in RFC3339 format
                (e.g., "2025-08-28T09:00:00-07:00").
            attendees (List[str], optional): A list of email addresses for attendees.
            recurrence (List[str], optional): A list of RRULE strings for
                recurring events following RFC 5545 specification. Examples:
                - Daily for 10 occurrences: ["RRULE:FREQ=DAILY;COUNT=10"]
                - Weekly on Monday and Wednesday: ["RRULE:FREQ=WEEKLY;BYDAY=MO,WE"]
                - Monthly on the last Friday: ["RRULE:FREQ=MONTHLY;BYDAY=-1FR"]
                - Every weekday: ["RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"]

        Returns:
            dict: The created event object.
        """
        logger.info(
            f"Creating calendar event: {summary} from {start_time} to {end_time}"
        )
        try:
            attendees_list: List[Dict[str, str] | List] = (
                [{"email": email} for email in attendees] if attendees else []
            )
            if attendees_list:
                logger.debug(f"Adding {len(attendees_list)} attendees to event")

            event: Dict = {
                "summary": summary,
                "location": location,
                "description": description,
                "start": {
                    "dateTime": start_time,
                    "timeZone": tzlocal.get_localzone_name(),
                },
                "end": {
                    "dateTime": end_time,
                    "timeZone": tzlocal.get_localzone_name(),
                },
                "attendees": attendees_list,
            }

            if recurrence:
                event["recurrence"] = recurrence
                logger.debug(f"Adding recurrence rules: {recurrence}")

            # pylint: disable=no-member
            created_event = (
                self.calendar_service.events()
                .insert(calendarId="primary", body=event)
                .execute()
            )

            event_id = created_event.get("id")
            logger.info(f"Successfully created calendar event with ID: {event_id}")
            return created_event
        except HttpError as error:
            logger.error(f"Failed to create calendar event '{summary}': {error}")
            raise HttpError from error

    def read_paragraph_element(self, element):
        """Returns the text from a TextRun element."""
        text_run = element.get("textRun")
        if not text_run:
            return ""
        return text_run.get("content", "")

    def read_structural_elements(self, elements):
        """
        Recursively reads the content of structural elements in the document.
        A Google Doc's content is a list of these elements.
        """
        text = ""
        for value in elements:
            if "paragraph" in value:
                paragraph_elements = value.get("paragraph").get("elements")
                for elem in paragraph_elements:
                    text += self.read_paragraph_element(elem)
            elif "table" in value:
                # The text in a table is in cells.
                table = value.get("table")
                for row in table.get("tableRows"):
                    cells = row.get("tableCells")
                    for cell in cells:
                        text += self.read_structural_elements(cell.get("content"))
            elif "tableOfContents" in value:
                # The text in the TOC is also in a structural element.
                toc = value.get("tableOfContents")
                text += self.read_structural_elements(toc.get("content"))
        return text

    def get_google_doc_title(self, document_id: str) -> str | None:
        """Gets a google doc file title"""
        logger.info(f"Getting title for document: {document_id}")

        # Check cache first
        cached_title = self.cache.get_document_title(document_id)
        if cached_title:
            logger.debug(f"Retrieved title from cache: {cached_title}")
            return cached_title

        try:
            # Retrieve the document from the API
            # pylint: disable=no-member
            document = (
                self.docs_service.documents()
                .get(documentId=document_id, fields="title")
                .execute()
            )

            title = document.get("title")
            logger.info(f"Successfully retrieved document title: {title}")
            return title

        except HttpError as err:
            logger.error(f"HTTP error occurred: {err}")
            if err.resp.status == 404:
                error_msg = (
                    "The requested document was not found."
                    "Please check the DOCUMENT_ID."
                )
                logger.warning(f"Document not found: {document_id}")
                return error_msg
        except FileNotFoundError:
            error_msg = "Error: `credentials.json` not found."
            logger.error(error_msg)
            return error_msg
        # pylint: disable=broad-exception-caught
        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}"
            logger.error(error_msg)
            return error_msg

        return None

    def fetch_google_doc_content(self, document_id: str) -> str | None:
        """
        Fetches and returns the text content of a Google Doc.

        Args:
            document_id: The ID of the Google Doc to fetch.

        Returns:
            A string containing the text content of the document,
            or None if an error occurs.
        """
        logger.info(f"Fetching content for document: {document_id}")

        # Check cache first
        logger.debug("Try fetching document content from cache")
        cached_content = self.cache.get_document_content(document_id)
        if cached_content:
            logger.debug("Retrieved document content from cache")
            return cached_content

        try:
            # Retrieve the document from the API
            # pylint: disable=no-member
            document = (
                self.docs_service.documents().get(documentId=document_id).execute()
            )

            logger.debug("Document retrieved successfully from API")

            title = document.get("title")
            logger.info(f"Document title: {title}")

            # Extract the text from the document's body
            doc_content = document.get("body").get("content")

            # Parse the structural elements to get the plain text
            text_content = self.read_structural_elements(doc_content)

            # Cache the content
            self.cache.set_document_content(document_id, text_content, title)

            length = len(text_content)
            logger.info(
                f"Successfully extracted text content from document, "
                f"length: {length} characters"
            )
            config = get_config()

            if length > config.config.max_document_length:
                logger.warning(
                    f"Document content length ({length}) exceeds the maximum "
                    f"allowed ({config.config.max_document_length}). "
                    "Truncating content."
                )
                return "Document exceeds maximum length please read as paragraphs"

            return text_content

        except HttpError as err:
            logger.error(f"HTTP API error occurred: {err}")
            if err.resp.status == 404:
                logger.warning(
                    f"Document not found: {document_id}. Please check the DOCUMENT_ID."
                )
            return None
        except FileNotFoundError:
            logger.error("credentials.json not found")
            logger.info("Please follow the setup instructions in the script's comments")
            return None
        # pylint: disable=broad-exception-caught
        except Exception as e:
            logger.error(f"Unexpected error occurred: {e}")
            return None
