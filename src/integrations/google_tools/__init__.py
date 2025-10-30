"""
Initialize Google tools specs
"""

from src.integrations.google_tools.gmail_tools import GmailToolSpec
from src.integrations.google_tools.google_tools import GoogleToolSpec

__all__ = ["GoogleToolSpec", "GmailToolSpec"]
