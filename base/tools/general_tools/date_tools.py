from datetime import date, datetime
from llama_index.core.tools.tool_spec.base import BaseToolSpec


class DateToolsSpecs(BaseToolSpec):
    spec_functions = [
        "get_date",
        "get_time"
    ]

    def __init__(self):
        pass

    def get_date(self) -> str:
        """Returns a string containing todays date in the format YYYY-MM-DD"""
        return date.today().__str__()

    def get_time(self) -> str:
        """Returns the current time"""
        return datetime.now().time().__str__()
