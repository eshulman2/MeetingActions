"""Jira tools specs"""

from typing import Any, Dict, List

from jira import JIRA, JIRAError
from jira.resources import Issue
from llama_index.core.tools.tool_spec.base import BaseToolSpec

from .jira_formatter import JiraFormatter


class JiraToolSpec(BaseToolSpec):
    """Jira tools specs"""

    spec_functions = [
        "get_jira_issue",
        "list_projects",
        "add_comment",
        "search_jira_issues",
        "create_jira_issue",
        "get_all_available_fields",
    ]

    def __init__(self, api_token: str, server: str):
        self.jira_client = JIRA(server=server, token_auth=api_token)

    def get_fields_name_to_id(self) -> Dict[str, str]:
        """Get mapping of field name to jira field id.
        all names will be using lower()"""
        try:
            return {f["name"].lower(): f["id"] for f in self.jira_client.fields()}
        except JIRAError as e:
            raise JIRAError from e

    def get_fields_id_to_name(self) -> Dict[str, str]:
        """Get mapping of field name to jira field id"""
        try:
            return {f["id"]: f["name"] for f in self.jira_client.fields()}
        except JIRAError as e:
            raise JIRAError from e

    def get_all_available_fields(self) -> List[str]:
        """Get list of all available jira fields by their name"""
        try:
            return [f["name"] for f in self.jira_client.fields()]
        except JIRAError as e:
            raise JIRAError from e

    def get_fields_id_to_types(self):
        """Get mapping of field id to jira field type"""
        return {
            f["id"]: f.get("schema", {}).get("type", "unavailable")
            for f in self.jira_client.fields()
        }

    def list_projects(self) -> List[str]:
        """List all projects viewable by user"""
        try:
            projects = self.jira_client.projects()
            return sorted(project.key for project in projects)
        except JIRAError as e:
            raise JIRAError from e

    def add_comment(self, issue: str, comment: str) -> None:
        """Add comment on a jira issue"""
        try:
            self.jira_client.add_comment(issue, comment)
        except JIRAError as e:
            raise JIRAError from e

    def search_jira_issues(
        self, query: str, max_results: int | None = 50
    ) -> list[Issue]:
        """Searches jira issues using JQL (Jira query langue).
        Returns 50 results by default, for more results set max_results"""
        try:
            return self.jira_client.search_issues(query, maxResults=max_results)
        except JIRAError as e:
            raise JIRAError from e

    def create_jira_issue(
        self, issue_fields: Dict, issue_type: str = "task"
    ) -> Issue:
        """
        Create a new Jira issue using the provided field values.

        This method takes a dictionary of Jira field names and their
        corresponding values, formats them according to their expected types,
        and creates a new issue in Jira. The issue type can be specified;
        if not provided, it defaults to 'task'.

        Args:
            issue_fields (Dict): A dictionary mapping Jira field names to
            their values.
            issue_type (str | None, optional): The type of Jira issue
                to create (e.g., 'Task', 'Bug'). Defaults to 'task'.

        Returns:
            Issue: The newly created Jira issue object.

        Raises:
            JIRAError: If there is an error during issue creation.
        """
        fields_ids_to_types = self.get_fields_id_to_types()
        fields_names_to_id = self.get_fields_name_to_id()
        issue = {}

        try:
            for field, value in issue_fields.items():
                formatter = getattr(
                    JiraFormatter,
                    fields_ids_to_types.get(fields_names_to_id.get(field), "any"),
                )
                issue[fields_names_to_id.get(field)] = formatter(value)

            issue["issuetype"] = JiraFormatter.issue_type(issue_type.capitalize())

            new_issue = self.jira_client.create_issue(fields=issue)

            return new_issue
        except JIRAError as e:
            raise JIRAError from e

    def get_jira_issue(
        self,
        issue_key: str,
        all_fields: bool | None = False,
        field_filter: List[str] | None = None,
    ) -> Dict[str, Any]:
        """
        Retrieve details of a Jira issue by its key.
        Args:
            issue_key (str): The key of the Jira issue to retrieve.
            all_fields (bool | None, optional): If True, returns all available
                fields for the issue. If False or None,
                returns only the fields specified in `field_filter`.
            field_filter (List[str] | None, optional): List of field names to
                retrieve. If None, defaults to ['assignee', 'status',
                'description', 'summary'].
        Returns:
            Dict[str, Any]: A dictionary containing the requested fields and
                their values.
        Raises:
            JIRAError: If there is an error retrieving the issue from Jira.
        """
        try:
            issue = self.jira_client.issue(issue_key)
        except JIRAError as e:
            raise JIRAError from e

        if all_fields:
            issue_dict = {}

            fields_mapping = self.get_fields_id_to_name()

            issue_dict = {
                fields_mapping[k]: v for k, v in issue.raw.get("fields").items()
            }
        else:
            if field_filter is None:
                field_filter = ["assignee", "status", "description", "summary"]

            fields_mapping = self.get_fields_name_to_id()

            issue_dict = {
                f: issue.get_field(fields_mapping[f.lower()]) for f in field_filter
            }

        return issue_dict
