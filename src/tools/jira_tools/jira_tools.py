"""Jira tools specs"""
from typing import List, Dict
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
        "create_jira_issue"
    ]

    def __init__(self, api_token, server):
        self.jira_client = JIRA(server=server,
                                token_auth=api_token)

    def get_jira_issue(self, issue_key: str) -> Issue:
        """Get jira issue by issue key"""
        try:
            return self.jira_client.issue(issue_key)
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
            new_issue = self.jira_client.create_issue(fields=issue_dict)
            return new_issue
        except JIRAError as e:
            raise JIRAError from e
