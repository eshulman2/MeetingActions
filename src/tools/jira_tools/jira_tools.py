"""Jira tools specs"""
from typing import List, Dict, Any
from llama_index.core.tools.tool_spec.base import BaseToolSpec
from jira import JIRA, JIRAError
from jira.resources import Issue


class JiraToolSpec(BaseToolSpec):
    """Jira tools specs"""
    spec_functions = [
        "get_jira_issue",
        "list_projects",
        "add_comment",
        "search_jira_issues",
        "create_jira_issue",
        "get_field_name_to_id",
        "get_all_fields"
    ]

    def __init__(self, api_token: str, server: str):
        self.jira_client = JIRA(server=server,
                                token_auth=api_token)
        self.fields = self.jira_client.fields()

    def get_field_name_to_id(self) -> Dict:
        """Get mapping of field name to jira field id"""
        return {f['name']: f['id'] for f in self.fields}

    def get_all_fields(self) -> List[str]:
        """Get list of all available jira fields"""
        return [f['name'] for f in self.fields]

    def get_jira_issue(
        self,
        issue_key: str,
        field_filter: List[str] | None = None
    ) -> dict[str:Any]:
        """
        Get jira issue by issue key and fields to filter.
        Default filter fields are:
        'assignee', 'status', 'description', 'summary'
        """
        if field_filter is None:
            field_filter = ['assignee',
                            'status', 'description', 'summary']
        try:
            issue = self.jira_client.issue(issue_key)
            issue_dict = {}

            fields_mapping = self.get_field_name_to_id()

            for f in field_filter:
                field = issue.get_field(fields_mapping[f])
                if not isinstance(field, str):
                    field = getattr(field, 'name', field)
                issue_dict[f] = field

            return issue_dict

        except JIRAError as e:
            raise JIRAError from e

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

    def search_jira_issues(self, query: str,
                           max_results: int | None = 50) -> list[Issue]:
        """Searches jira issues using JQL (Jira query langue)"""
        try:
            return self.jira_client.search_issues(query,
                                                  maxResults=max_results)
        except JIRAError as e:
            raise JIRAError from e

    def create_jira_issue(self, issue_dict: Dict) -> Issue:
        """Creates a single Jira issue using a dictionary of Jira
        fields and values"""
        try:
            fields_mapping = self.get_field_name_to_id()
            new_issue_dict = {
                fields_mapping[key]: value for key, value in issue_dict.items()
            }
            new_issue = self.jira_client.create_issue(fields=new_issue_dict)
            return new_issue
        except JIRAError as e:
            raise JIRAError from e
