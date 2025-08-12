"""Google Docs tools specs"""
from tools.google_tools.utils import authenticate
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from llama_index.core.tools.tool_spec.base import BaseToolSpec


class DocsToolSpec(BaseToolSpec):
    """Google Docs tools specs"""
    spec_functions = [
        "get_google_doc_title",
        "fetch_google_doc_content"
    ]

    def __init__(self):
        self.service = build("docs", "v1", credentials=authenticate())

    def read_paragraph_element(self, element):
        """Returns the text from a TextRun element."""
        text_run = element.get('textRun')
        if not text_run:
            return ''
        return text_run.get('content', '')

    def read_structural_elements(self, elements):
        """
        Recursively reads the content of structural elements in the document.
        A Google Doc's content is a list of these elements.
        """
        text = ''
        for value in elements:
            if 'paragraph' in value:
                paragraph_elements = value.get('paragraph').get('elements')
                for elem in paragraph_elements:
                    text += self.read_paragraph_element(elem)
            elif 'table' in value:
                # The text in a table is in cells.
                table = value.get('table')
                for row in table.get('tableRows'):
                    cells = row.get('tableCells')
                    for cell in cells:
                        text += self.read_structural_elements(
                            cell.get('content'))
            elif 'tableOfContents' in value:
                # The text in the TOC is also in a structural element.
                toc = value.get('tableOfContents')
                text += self.read_structural_elements(toc.get('content'))
        return text

    def get_google_doc_title(self, document_id: str) -> str:
        """Gets a google doc file title"""
        try:
            # Retrieve the document from the API
            # pylint: disable=no-member
            document = self.service.documents().get(
                documentId=document_id).execute()

            title = document.get('title')
            return title

        except HttpError as err:
            if err.resp.status == 404:
                return "The requested document was not found. Please check the DOCUMENT_ID."
        except FileNotFoundError:
            return "Error: `credentials.json` not found."
        # pylint: disable=broad-exception-caught
        except Exception as e:
            return f"An unexpected error occurred: {e}"

        return None

    def fetch_google_doc_content(self, document_id: str) -> str:
        """
        Fetches and returns the text content of a Google Doc.

        Args:
            document_id: The ID of the Google Doc to fetch.

        Returns:
            A string containing the text content of the document, or None if an error occurs.
        """
        try:
            # Retrieve the document from the API
            # pylint: disable=no-member
            document = self.service.documents().get(
                documentId=document_id).execute()

            print(f"The title of the document is: {document.get('title')}")

            # Extract the text from the document's body
            doc_content = document.get('body').get('content')

            # Parse the structural elements to get the plain text
            text_content = self.read_structural_elements(doc_content)

            return text_content

        except HttpError as err:
            print(f"An API error occurred: {err}")
            if err.resp.status == 404:
                print(
                    "The requested document was not found. Please check the DOCUMENT_ID.")
            return None
        except FileNotFoundError:
            print("Error: `credentials.json` not found.")
            print("Please follow the setup instructions in the script's comments.")
            return None
        # pylint: disable=broad-exception-caught
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return None
