"""
Initialize Google tools specs
"""

from src.integrations.google.tools import GoogleToolSpec
from src.integrations.google_tools.gmail_tools import GmailToolSpec

__all__ = ["GoogleToolSpec", "GmailToolSpec"]
