# Action Items Chat Client

An interactive command-line interface for managing the action items workflow. This client provides a conversational experience for generating, reviewing, editing, and dispatching action items to agents.

## Features

- **Generate Action Items**: Retrieve meeting notes and generate action items automatically
- **Interactive Review**: View generated action items in a formatted table
- **Edit Capabilities**:
  - Edit existing action items (title, description, assignee, due date, priority)
  - Add new action items
  - Remove unwanted action items
- **Approval Workflow**: Review and confirm before dispatching to agents
- **Dispatch Management**: Send approved action items to agents for execution
- **Results Display**: View execution results with success/failure status

## Installation

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

The client requires:
- `rich`: For beautiful terminal formatting and tables
- `prompt-toolkit`: For interactive dialogs and input
- `requests`: For API communication

## Usage

### Basic Usage

Start the client with default settings (connects to `http://localhost:8000`):

```bash
python src/clients/action_items_chat_client.py
```

### Custom Server URL

Specify a custom action items server URL:

```bash
python src/clients/action_items_chat_client.py --url http://your-server:8000
```

## Workflow Steps

### 1. Meeting Information
Enter the meeting name/identifier and date when prompted:
- **Meeting Name**: Name or identifier of the meeting (e.g., "Weekly Standup", "Project Planning")
- **Date**: Meeting date in YYYY-MM-DD format

### 2. Generate Action Items
The client automatically calls the `/generate` endpoint to:
- Retrieve meeting notes
- Generate structured action items
- Display them in a formatted table

### 3. Review and Edit
Review the generated action items with these options:
- **Approve & Dispatch**: Confirm and send to agents for execution
- **Edit Item**: Modify an existing action item's fields
- **Add Item**: Create a new action item
- **Remove Item**: Delete an action item
- **Cancel**: Exit without dispatching

#### Editing Action Items
When editing, you can modify:
- Title
- Description
- Assignee
- Due Date
- Priority (low/medium/high/urgent)

### 4. Dispatch to Agents
After approval, action items are sent to the `/dispatch` endpoint where:
- Items are routed to appropriate agents
- Agent-specific instructions are generated
- Agents execute the tasks
- Results are collected

### 5. View Results
The client displays:
- Execution results table showing agent, status, and result
- Summary statistics (successful/total executions)
- Color-coded success/failure indicators

## API Endpoints Used

The client interacts with two main endpoints:

### POST /generate
Generates action items from meeting information.

**Request:**
```json
{
  "meeting": "string",
  "date": "YYYY-MM-DD"
}
```

**Response:**
```json
{
  "action_items": {
    "meeting_title": "string",
    "meeting_date": "YYYY-MM-DD",
    "action_items": [
      {
        "title": "string",
        "description": "string",
        "assignee": "string",
        "due_date": "YYYY-MM-DD",
        "priority": "string",
        "category": "string"
      }
    ]
  }
}
```

### POST /dispatch
Dispatches action items to agents for execution.

**Request:**
```json
{
  "action_items": {
    "meeting_title": "string",
    "meeting_date": "YYYY-MM-DD",
    "action_items": [...]
  }
}
```

**Response:**
```json
{
  "results": [
    {
      "action_item_index": 0,
      "agent_name": "string",
      "success": true,
      "result": "string",
      "error_message": null
    }
  ]
}
```

## Example Session

```
╭─────────────────────────────────────────────────────────╮
│ Action Items Workflow Assistant                        │
│                                                         │
│ I'll help you generate and execute action items from   │
│ meeting notes. You can review and edit items before    │
│ dispatching them to agents.                            │
╰─────────────────────────────────────────────────────────╯

Step 1: Meeting Information

[Dialog: Enter meeting name]
Meeting: Weekly Team Sync

[Dialog: Enter date]
Date: 2025-10-19

Step 2: Generating Action Items

Meeting: Weekly Team Sync
Date: 2025-10-19

✓ Action items generated successfully!

Step 3: Review and Edit Action Items

┌─────────────────────────────────────────────────────────┐
│              Generated Action Items                     │
├───┬──────────────┬────────────────┬─────────┬──────────┤
│ # │ Title        │ Description    │ Assignee│ Due Date │
├───┼──────────────┼────────────────┼─────────┼──────────┤
│ 1 │ Update docs  │ Update API...  │ John    │ 2025-10-20
│ 2 │ Fix bug #123 │ Fix login...   │ Sarah   │ 2025-10-21
└───┴──────────────┴────────────────┴─────────┴──────────┘

[Dialog: Review Action Items]
> Approve & Dispatch

Step 4: Dispatching to Agents

✓ Action items dispatched successfully!

Execution Results

┌───┬────────────────┬─────────┬───────────────────────┐
│ # │ Agent          │ Status  │ Result                │
├───┼────────────────┼─────────┼───────────────────────┤
│ 1 │ jira-agent     │ Success │ Created ticket PROJ-1│
│ 2 │ github-agent   │ Success │ Created issue #456   │
└───┴────────────────┴─────────┴───────────────────────┘

╭───────────────────────────────╮
│ Summary: 2/2 executions       │
│ successful                    │
╰───────────────────────────────╯

Workflow completed successfully!
```

## Error Handling

The client handles various error scenarios:
- **Network errors**: Connection issues with the server
- **Invalid input**: Incorrect date formats, invalid item numbers
- **Server errors**: API failures or timeouts
- **Empty results**: No action items generated

All errors are displayed with clear messages and appropriate guidance.

## Development

### Adding Features

The client is organized into methods that handle specific workflows:
- `get_meeting_info()`: Collect user input
- `generate_action_items()`: Call generation endpoint
- `review_and_edit_loop()`: Interactive review process
- `edit_action_item()`: Single item editing
- `add_action_item()`: Add new items
- `remove_action_item()`: Delete items
- `dispatch_action_items()`: Send to agents
- `display_results()`: Show execution results

### Extending the Client

To add new functionality:
1. Add new methods to the `ActionItemsChatClient` class
2. Integrate them into the `run()` workflow
3. Use `rich` for formatted output
4. Use `prompt_toolkit` for user interactions

## Troubleshooting

**Client can't connect to server:**
- Verify the server is running: `curl http://localhost:8000/docs`
- Check the URL with `--url` parameter
- Ensure firewall allows connections

**Dialogs not displaying properly:**
- Ensure terminal supports ANSI colors
- Try running in a different terminal emulator
- Update `prompt-toolkit` and `rich` packages

**Action items generation fails:**
- Verify meeting notes exist for the specified date
- Check server logs for errors
- Ensure LLM service is configured correctly
