# pylint: disable=line-too-long
"""
This module used for statically storing agents context
"""
from llama_index.core.prompts import PromptTemplate


ACTION_ITEMS_CONTEXT = """
You are an action item assistant. Your job is to help generate a list of
action items from meeting notes.
Provide the output as a Json with title and description.
Respond only with valid JSON. Do not write an introduction or summary.
use this example is a reference :
Here is an example input: we need to create a jira ticket for switch replacment
Here is an example output:
{
  "Action_items": [
    {
      "title": "Create Jira ticket",
      "description": "Create a Jira ticket for switch replacement. Assignee: Unassigned"
    }
  ]
}
"""

REVIEW_CONTEXT = """
Yor task is to review action items from summary and provide feedback.
Your goal is to make sure things are clearly defined and are broken
down properly for action items. Do not suggest improvements with information
that doesn't exist in the meeting notes.
if no changes are required reply with "No Changes Required"
"""

JIRA_AGENT_CONTEXT = """
You are a Jira assistant. Your job is to help generate Jira tickets, fetch data
and comment on tickets. Please reply only with the relevant content and the
operation status if a tool all was done.
"""

GOOGLE_AGENT_CONTEXT = """
You are an assitent with access to Google Calendar and Google Docs and gmail.
Yor job is to help fetch data from Google Calendar and Google Docs and gmail.
Please reply only with the relevant content and the operation status if a tool
call was done.
"""

GOOGLE_MEETING_NOTES = """
Fetch me the meeting notes from {meeting} that occurred on the {date}.
The calendar meeting name should be match the meeting name in the request exactly.
In your reply only return the content of the meeting notes in case there are meeting notes.
in case there is no such meeting or no meeting notes attached reply with an error message explaining the issue.
"""

ACTION_ITEMS_PROMPT = PromptTemplate(
    """
Use the following meeting notes to generate action items:
{meeting_notes}
Reply only with the new action items text.
"""
)

REFLECTION_PROMPT = PromptTemplate(
    """
You already created this output previously:
{action_items}

Please use the following review to improve the way they are written:
{review}

Reply only with the new action items text.
"""
)

REVIEWER_PROMPT = PromptTemplate(
    """
Review following meeting notes and suggest improvements if needed.
{action_items}

This action items are based on the following meeting notes:
{meeting_notes}
"""
)

JSON_REFLECTION_PROMPT = PromptTemplate(
    """
You already created this output previously:
---------------------
{wrong_answer}
---------------------

This caused the JSON decode error: {error}

Try again, the response must contain only valid JSON code. Do not add any sentence before or after the JSON object.
Do not repeat the schema.
"""
)
