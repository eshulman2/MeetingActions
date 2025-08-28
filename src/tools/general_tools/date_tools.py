"""
Date related tools
"""

from datetime import date, datetime, timedelta

from llama_index.core.tools.tool_spec.base import BaseToolSpec


class DateToolsSpecs(BaseToolSpec):
    """Date tools specs for date related tools"""

    spec_functions = ["get_date", "get_time", "get_date_delta"]

    def __init__(self):
        pass

    def get_date(self) -> str:
        """Returns a string containing todays date in the format YYYY-MM-DD"""
        return str(date.today())

    def get_time(self) -> str:
        """Returns the current time"""
        return str(datetime.now().time())

    def get_date_delta(self, days: int) -> str:
        """Returns a string containing the date after adding days to today.
        This is useful for calculating tomorrow's date or any future date."""
        new_date = date.today() + timedelta(days=days)
        return str(new_date)
