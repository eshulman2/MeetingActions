"""Jira field formatting utilities for API requests."""


class JiraFormatter:
    """
    Utility class for formatting field values for Jira API requests.

    This class provides static methods to convert Python values into the
    specific JSON structures required by different Jira field types when
    making API calls to create or update issues.
    """

    @staticmethod
    def options(value):
        """
        Format a value for option/select type fields.

        Args:
            value: The option value to format

        Returns:
            dict: A dictionary with 'value' key containing the input value
        """
        return {"value": value}

    @staticmethod
    def user(value):
        """
        Format a value for user type fields.

        Args:
            value: The username or user identifier

        Returns:
            dict: A dictionary with 'name' key containing the username
        """
        return {"name": value}

    @staticmethod
    def array(value):
        """
        Format a list of values for array type fields.

        Args:
            value: A list of values to format

        Returns:
            list: A list of dictionaries, each containing a 'value' key
        """
        return [{"value": v for v in value}]

    @staticmethod
    def number(value):
        """
        Format a value for numeric type fields.

        Args:
            value: The numeric value to format

        Returns:
            The value unchanged (numeric values don't need transformation)
        """
        return value

    @staticmethod
    def string(value):
        """
        Format a value for string type fields.

        Args:
            value: The string value to format

        Returns:
            The value unchanged (string values don't need transformation)
        """
        return value

    @staticmethod
    def unavailable(value):
        """
        Format a value for unavailable/unknown type fields.

        Args:
            value: The value to format

        Returns:
            The value unchanged (fallback for unknown field types)
        """
        return value

    @staticmethod
    def any(value):
        """
        Format a value for generic/any type fields.

        Args:
            value: The value to format

        Returns:
            The value unchanged (generic handler for any field type)
        """
        return value

    @staticmethod
    def project(value):
        """
        Format a value for project type fields.

        Args:
            value: The project key or identifier

        Returns:
            dict: A dictionary with 'key' containing the project identifier
        """
        return {"key": value}

    @staticmethod
    def version(value):
        """
        Format a value for version type fields.

        Args:
            value: The version name or identifier

        Returns:
            dict: A dictionary with 'name' containing the version identifier
        """
        return {"name": value}

    @staticmethod
    def datetime(value):
        """
        Format a value for datetime type fields.

        Args:
            value: The datetime value in ISO format (yyyy-MM-dd'T'HH:mm:ss.SSSZ)

        Returns:
            The value unchanged (assumes input is already in correct format)

        Note:
            The datetime format must be: yyyy-MM-dd'T'HH:mm:ss.SSSZ
        """
        # format must be: yyyy-MM-dd'T'HH:mm:ss.SSSZ
        return value

    @staticmethod
    def issue_type(value):
        """
        Format a value for issue type fields.

        Args:
            value: The issue type name or identifier

        Returns:
            dict: A dictionary with 'name' containing the issue type identifier
        """
        return {"name": value}
