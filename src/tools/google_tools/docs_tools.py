"""Google Docs tools specs"""

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from llama_index.core.tools.tool_spec.base import BaseToolSpec

from src.configs.logging_config import get_logger

from .utils import authenticate

logger = get_logger("google_tools.docs")


class DocsToolSpec(BaseToolSpec):
    """Google Docs tools specs"""

    spec_functions = ["get_google_doc_title", "fetch_google_doc_content"]

    def __init__(self):
        logger.info("Initializing Google Docs tool spec")
        self.service = build("docs", "v1", credentials=authenticate())
        logger.debug("Google Docs service initialized successfully")

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
                        text += self.read_structural_elements(
                            cell.get("content")
                        )
            elif "tableOfContents" in value:
                # The text in the TOC is also in a structural element.
                toc = value.get("tableOfContents")
                text += self.read_structural_elements(toc.get("content"))
        return text

    def get_google_doc_title(self, document_id: str) -> str | None:
        """Gets a google doc file title"""
        logger.info(f"Getting title for document: {document_id}")
        try:
            # Retrieve the document from the API
            # pylint: disable=no-member
            document = (
                self.service.documents().get(documentId=document_id).execute()
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
        try:
            # Retrieve the document from the API
            # pylint: disable=no-member
            document = (
                self.service.documents().get(documentId=document_id).execute()
            )
            logger.debug("Document retrieved successfully from API")

            title = document.get("title")
            logger.info(f"Document title: {title}")

            # Extract the text from the document's body
            doc_content = document.get("body").get("content")

            # Parse the structural elements to get the plain text
            text_content = self.read_structural_elements(doc_content)

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
            logger.info(
                "Please follow the setup instructions in the script's comments"
            )
            return None
        # pylint: disable=broad-exception-caught
        except Exception as e:
            logger.error(f"Unexpected error occurred: {e}")
            return None
