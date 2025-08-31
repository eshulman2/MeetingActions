"""Google calendar tools specs"""

from datetime import datetime
from typing import Dict, List, Optional

import tzlocal
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from llama_index.core.tools.tool_spec.base import BaseToolSpec

from src.configs.logging_config import get_logger

from .utils import authenticate

logger = get_logger("google_tools.calendar")


class CalendarToolSpec(BaseToolSpec):
    """Google calendar tools specs"""

    spec_functions = [
        "get_event_gdoc_attachments_ids",
        "get_events_by_date",
        "create_event",
    ]

    def __init__(self):
        logger.info("Initializing Google Calendar tool spec")
        try:
            self.service = build("calendar", "v3", credentials=authenticate())
            logger.debug("Google Calendar service initialized successfully")
        except HttpError as error:
            logger.error(
                f"Failed to initialize Google Calendar service: {error}"
            )
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
                self.service.events()
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
                            logger.debug(
                                f"Found Google Doc attachment: {file_id}"
                            )

            else:
                logger.info("Event has no attachments")
                return "Event has no attachments."

            logger.info(f"Found {len(google_doc_ids)} Google Doc attachments")
            return google_doc_ids

        except HttpError as error:
            logger.error(
                f"Failed to get event attachments for {event_id}: {error}"
            )
            raise HttpError from error

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
        time_min = (
            datetime.combine(target_date, datetime.min.time()).isoformat()
            + "Z"
        )
        time_max = (
            datetime.combine(target_date, datetime.max.time()).isoformat()
            + "Z"
        )

        logger.info(
            f"Fetching events for {target_date.strftime('%Y-%m-%d')} "
            f"from calendar: {calendar_id}"
        )

        try:
            # Call the Calendar API
            # pylint: disable=no-member
            events_result = (
                self.service.events()
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

        Returns:
            dict: The created event object.
        """
        logger.info(
            f"Creating calendar event: {summary} from {start_time} to {end_time}"
        )
        try:
            attendees = (
                [{"email": email} for email in attendees] if attendees else []
            )
            if attendees:
                logger.debug(f"Adding {len(attendees)} attendees to event")

            event = {
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
                "attendees": attendees,
            }

            # pylint: disable=no-member
            created_event = (
                self.service.events()
                .insert(calendarId="primary", body=event)
                .execute()
            )

            event_id = created_event.get("id")
            logger.info(
                f"Successfully created calendar event with ID: {event_id}"
            )
            return created_event
        except HttpError as error:
            logger.error(
                f"Failed to create calendar event '{summary}': {error}"
            )
            raise HttpError from error
