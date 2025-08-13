"""Google calendar tools specs"""
from datetime import datetime
from typing import List, Dict
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from llama_index.core.tools.tool_spec.base import BaseToolSpec
from tools.google_tools.utils import authenticate


class CalendarToolSpec(BaseToolSpec):
    """Google calendar tools specs"""
    spec_functions = [
        "get_google_doc_attachment_ids",
        "get_events_by_date"
    ]

    def __init__(self):
        try:
            self.service = build('calendar', 'v3', credentials=authenticate())
        except HttpError as error:
            raise HttpError from error

    def get_google_doc_attachment_ids(self, event_id: str,
                                      calendar_id: str = 'primary'
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
        google_doc_ids = []
        google_doc_mime_type = "application/vnd.google-apps.document"
        try:
            # Call the Calendar API to get the specific event
            # pylint: disable=no-member
            event = self.service.events().get(
                calendarId=calendar_id, eventId=event_id).execute()

            # Check if the 'attachments' key exists in the event object
            if 'attachments' in event:
                for attachment in event['attachments']:
                    # Check if the attachment is a Google Doc by its MIME type
                    if attachment.get('mimeType') == google_doc_mime_type:
                        file_id = attachment.get('fileId')
                        if file_id:
                            google_doc_ids.append(file_id)

            else:
                return "Event has no attachments."

        except HttpError as error:
            # Handle common errors
            return f"Error: {error}"

        return google_doc_ids

    def get_events_by_date(self, year: int, month: int, day: int,
                           calendar_id: str = 'primary') -> List[Dict]:
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
        time_min = datetime.combine(
            target_date, datetime.min.time()).isoformat() + 'Z'
        time_max = datetime.combine(
            target_date, datetime.max.time()).isoformat() + 'Z'

        print(f"Fetching events for {target_date.strftime('%Y-%m-%d')}...")

        try:
            # Call the Calendar API
            # pylint: disable=no-member
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])
            return events

        except HttpError as error:
            print(f'An error occurred: {error}')
            return None
