"""Simple CLI Client for Action Items Workflow.

This client provides a clean command-line interface without TUI dialogs for:
1. Generating action items from meeting information
2. Reviewing and editing generated action items
3. Dispatching approved action items to agents for execution
"""

import argparse
import sys
from datetime import datetime
from typing import Any

import httpx
from rich.console import Console
from rich.table import Table

from src.core.base.retry import BackoffStrategy, with_retry

console = Console()


class ActionItemsSimpleClient:
    """Simple CLI client for action items workflow."""

    def __init__(self, base_url: str = "http://localhost:8002"):
        """Initialize the client.

        Args:
            base_url: Base URL of the action items server
        """
        self.base_url = base_url
        self.action_items = None

    @with_retry(
        max_attempts=3,
        backoff=BackoffStrategy.EXPONENTIAL,
        base_delay=2.0,
        max_delay=30.0,
        retryable_exceptions=(
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.NetworkError,
            httpx.HTTPStatusError,
        ),
    )
    def _post_with_retry(
        self, endpoint: str, json_data: dict, timeout: float = 120.0
    ) -> dict:
        """Make a POST request with retry logic.

        Args:
            endpoint: API endpoint (relative to base_url)
            json_data: JSON data to send
            timeout: Request timeout in seconds

        Returns:
            Response JSON data

        Raises:
            httpx.HTTPStatusError: If request fails after retries
            httpx.TimeoutException: If request times out after retries
        """
        with httpx.Client(timeout=timeout) as client:
            response = client.post(f"{self.base_url}{endpoint}", json=json_data)
            response.raise_for_status()
            return response.json()

    def display_welcome(self):
        """Display welcome message."""
        console.print()
        console.print(
            "[bold cyan]═══════════════════════════════════════════════[/bold cyan]"
        )
        console.print("[bold cyan]    Action Items Workflow Assistant[/bold cyan]")
        console.print(
            "[bold cyan]═══════════════════════════════════════════════[/bold cyan]"
        )
        console.print()
        console.print(
            "I'll help you generate and execute action items from meeting notes."
        )
        console.print(
            "You can review and edit items before dispatching them to agents."
        )
        console.print()

    def get_input(self, prompt: str, default: str | None = None) -> str | None:
        """Get user input with optional default.

        Args:
            prompt: Prompt to display
            default: Default value if user presses enter

        Returns:
            User input or default
        """
        if default:
            full_prompt = f"{prompt} [{default}]: "
        else:
            full_prompt = f"{prompt}: "

        console.print(f"[cyan]{full_prompt}[/cyan]", end="")
        value = input().strip()
        return value if value else default

    def get_yes_no(self, prompt: str, default: bool = False) -> bool:
        """Get yes/no confirmation from user.

        Args:
            prompt: Question to ask
            default: Default value

        Returns:
            True for yes, False for no
        """
        default_str = "Y/n" if default else "y/N"
        console.print(f"[cyan]{prompt} ({default_str}):[/cyan] ", end="")
        response = input().strip().lower()

        if not response:
            return default
        return response in ["y", "yes"]

    def get_meeting_info(self) -> tuple[str, str]:
        """Get meeting information from user.

        Returns:
            Tuple of (meeting_name, date)
        """
        console.print("\n[bold cyan]Step 1: Meeting Information[/bold cyan]\n")

        meeting = self.get_input("Enter meeting name/identifier")
        if not meeting:
            console.print("[red]Meeting name is required. Exiting.[/red]")
            sys.exit(1)

        while True:
            date_str = self.get_input(
                "Enter meeting date (YYYY-MM-DD)", datetime.now().strftime("%Y-%m-%d")
            )

            if not date_str:
                console.print("[red]Date is required. Exiting.[/red]")
                sys.exit(1)

            try:
                datetime.strptime(date_str, "%Y-%m-%d")
                return meeting, date_str
            except ValueError:
                console.print("[red]Invalid date format. Please use YYYY-MM-DD[/red]")

    def generate_action_items(self, meeting: str, date: str) -> dict:
        """Generate action items from meeting information.

        Args:
            meeting: Meeting name/identifier
            date: Meeting date

        Returns:
            Generated action items response
        """
        console.print("\n[bold cyan]Step 2: Generating Action Items[/bold cyan]\n")
        console.print(f"Meeting: [green]{meeting}[/green]")
        console.print(f"Date: [green]{date}[/green]\n")

        with console.status("[bold green]Generating action items..."):
            try:
                result = self._post_with_retry(
                    "/generate", {"meeting": meeting, "date": date}, timeout=120.0
                )

                console.print("[green]✓[/green] Action items generated successfully!\n")
                return result

            except (
                httpx.HTTPStatusError,
                httpx.TimeoutException,
                httpx.NetworkError,
            ) as e:
                console.print(f"[red]Error generating action items: {e}[/red]")
                console.print(
                    "[yellow]Please check that the server is running "
                    "and try again.[/yellow]"
                )
                sys.exit(1)
            except Exception as e:
                console.print(f"[red]Unexpected error: {e}[/red]")
                sys.exit(1)

    def display_action_items(self, action_items: dict, title: str | None = None):
        """Display action items in a formatted table.

        Args:
            action_items: Action items data
            title: Optional custom title
        """
        table = Table(
            title=title or "Action Items", show_header=True, header_style="bold cyan"
        )
        table.add_column("#", style="dim", width=4)
        table.add_column("Title", style="cyan", width=30)
        table.add_column("Description", style="white", width=40)
        table.add_column("Assignee", style="green", width=15)
        table.add_column("Due Date", style="yellow", width=12)
        table.add_column("Priority", style="magenta", width=10)

        items = action_items.get("action_items", [])
        for idx, item in enumerate(items, 1):
            desc = item.get("description", "N/A")
            if len(desc) > 40:
                desc = desc[:37] + "..."

            table.add_row(
                str(idx),
                item.get("title", "N/A"),
                desc,
                item.get("assignee", "TBD"),
                str(item.get("due_date", "TBD")),
                item.get("priority", "medium"),
            )

        console.print(table)
        console.print()

    def display_single_action_item(self, item: dict, index: int, total: int):
        """Display a single action item in detail.

        Args:
            item: Action item data
            index: Current item index (1-based)
            total: Total number of items
        """
        console.print()
        console.print(f"[bold cyan]━━━ Action Item {index} of {total} ━━━[/bold cyan]")
        console.print()

        console.print(f"[bold cyan]Title:[/bold cyan] {item.get('title', 'N/A')}")
        console.print(
            f"[bold cyan]Description:[/bold cyan] {item.get('description', 'N/A')}"
        )
        console.print(f"[bold cyan]Assignee:[/bold cyan] {item.get('assignee', 'TBD')}")
        console.print(f"[bold cyan]Due Date:[/bold cyan] {item.get('due_date', 'TBD')}")
        console.print(
            f"[bold cyan]Priority:[/bold cyan] {item.get('priority', 'medium')}"
        )
        console.print(
            f"[bold cyan]Category:[/bold cyan] {item.get('category', 'general')}"
        )
        console.print()

    def review_single_item(self, item: dict, index: int, total: int) -> str:
        """Review a single action item.

        Args:
            item: Action item data
            index: Current item index (1-based)
            total: Total number of items

        Returns:
            User's choice: 'approve', 'edit', 'remove', or 'back'
        """
        self.display_single_action_item(item, index, total)

        console.print("[bold]Actions:[/bold]")
        console.print("  [cyan]a[/cyan] - Approve this item")
        console.print("  [cyan]e[/cyan] - Edit this item")
        console.print("  [cyan]r[/cyan] - Remove this item")
        if index > 1:
            console.print("  [cyan]b[/cyan] - Back to previous item")
        console.print()

        while True:
            choice = self.get_input(
                "What would you like to do? (a/e/r" + ("/b" if index > 1 else "") + ")"
            )
            if not choice:
                console.print("[yellow]Invalid choice. Please try again.[/yellow]")
                continue
            choice = choice.lower()

            if choice == "a":
                return "approve"
            if choice == "e":
                return "edit"
            if choice == "r":
                return "remove"
            if choice == "b" and index > 1:
                return "back"

            console.print("[yellow]Invalid choice. Please try again.[/yellow]")

    def review_and_edit_loop(self, action_items_response: dict) -> dict:
        """Allow user to review and edit action items one by one.

        Args:
            action_items_response: Action items response from server

        Returns:
            Approved action items (possibly modified)
        """
        console.print("\n[bold cyan]Step 3: Review and Edit Action Items[/bold cyan]\n")

        action_items_data = action_items_response["action_items"]
        items = action_items_data.get("action_items", [])

        if not items:
            console.print("[yellow]No action items to review.[/yellow]")
            return action_items_data

        # First, show overview
        self.display_action_items(action_items_data, "Generated Action Items")
        console.print("[bold cyan]Let's review each item individually...[/bold cyan]\n")

        current_index = 0

        while current_index < len(items):
            item = items[current_index]
            choice = self.review_single_item(item, current_index + 1, len(items))

            if choice == "approve":
                console.print("[green]✓[/green] Action item approved\n")
                current_index += 1
            elif choice == "edit":
                items[current_index] = self.edit_single_item(item)
                console.print("[green]✓[/green] Action item updated\n")
            elif choice == "remove":
                if self.get_yes_no(f"Remove '{item.get('title', 'N/A')}'?", False):
                    items.pop(current_index)
                    console.print("[green]✓[/green] Action item removed\n")
                else:
                    current_index += 1
            elif choice == "back":
                current_index -= 1

        return self.final_approval(action_items_data)

    def edit_single_item(self, item: dict) -> dict:
        """Edit fields of a single action item.

        Args:
            item: Action item data to edit

        Returns:
            Updated action item
        """
        console.print("\n[bold cyan]Edit Action Item[/bold cyan]\n")

        while True:
            console.print("[bold]Fields:[/bold]")
            console.print("  1. Title")
            console.print("  2. Description")
            console.print("  3. Assignee")
            console.print("  4. Due Date")
            console.print("  5. Priority")
            console.print("  6. Category")
            console.print("  0. Done editing")
            console.print()

            choice = self.get_input("Select field to edit (0-6)")

            if choice == "0":
                break
            if choice == "1":
                item["title"] = self.get_input("New title", item.get("title", ""))
            elif choice == "2":
                item["description"] = self.get_input(
                    "New description", item.get("description", "")
                )
            elif choice == "3":
                item["assignee"] = self.get_input(
                    "New assignee", item.get("assignee", "TBD")
                )
            elif choice == "4":
                item["due_date"] = self.get_input(
                    "New due date (YYYY-MM-DD)", str(item.get("due_date", "TBD"))
                )
            elif choice == "5":
                item["priority"] = self.get_input(
                    "New priority (low/medium/high/urgent)",
                    item.get("priority", "medium"),
                )
            elif choice == "6":
                item["category"] = self.get_input(
                    "New category", item.get("category", "general")
                )
            else:
                console.print("[yellow]Invalid choice[/yellow]")
                continue

            console.print("[green]✓[/green] Field updated\n")

        return item

    def final_approval(self, action_items_data: dict) -> dict:
        """Show final summary and get user approval.

        Args:
            action_items_data: Action items data after individual review

        Returns:
            Approved action items or exits if cancelled
        """
        console.print()
        console.print(
            "[bold cyan]═══════════════════════════════════════════════[/bold cyan]"
        )
        console.print("[bold cyan]    Final Review - All Action Items[/bold cyan]")
        console.print(
            "[bold cyan]═══════════════════════════════════════════════[/bold cyan]"
        )
        console.print()

        items = action_items_data.get("action_items", [])

        if not items:
            console.print("[yellow]No action items to dispatch.[/yellow]")
            sys.exit(0)

        self.display_action_items(action_items_data, "Final Action Items")
        console.print(f"[bold]Total items: [cyan]{len(items)}[/cyan][/bold]\n")

        console.print("[bold]Options:[/bold]")
        console.print("  [cyan]d[/cyan] - Dispatch to agents")
        console.print("  [cyan]a[/cyan] - Add new item")
        console.print("  [cyan]r[/cyan] - Review items again")
        console.print("  [cyan]c[/cyan] - Cancel")
        console.print()

        while True:
            choice = self.get_input("What would you like to do? (d/a/r/c)")
            if not choice:
                console.print("[yellow]Invalid choice. Please try again.[/yellow]")
                continue
            choice = choice.lower()

            if choice == "d":
                if self.get_yes_no(
                    f"Dispatch {len(items)} action item(s) to agents?", True
                ):
                    return action_items_data
            elif choice == "a":
                action_items_data = self.add_action_item(action_items_data)
                return self.final_approval(action_items_data)
            elif choice == "r":
                console.print(
                    "\n[bold cyan]Returning to individual review...[/bold cyan]\n"
                )
                return self.review_and_edit_loop({"action_items": action_items_data})
            elif choice == "c":
                console.print("[yellow]Operation cancelled.[/yellow]")
                sys.exit(0)
            else:
                console.print("[yellow]Invalid choice. Please try again.[/yellow]")

    def add_action_item(self, action_items_data: dict) -> dict:
        """Add a new action item.

        Args:
            action_items_data: Current action items data

        Returns:
            Updated action items data
        """
        console.print("\n[bold cyan]Adding New Action Item[/bold cyan]\n")

        title = self.get_input("Title")
        if not title:
            console.print("[yellow]Title is required. Skipping.[/yellow]")
            return action_items_data

        description = self.get_input("Description", "N/A")
        assignee = self.get_input("Assignee", "TBD")
        due_date = self.get_input("Due date (YYYY-MM-DD)", "TBD")
        priority = self.get_input("Priority (low/medium/high/urgent)", "medium")
        category = self.get_input("Category", "general")

        new_item: dict[str, Any] = {
            "title": title,
            "description": description,
            "assignee": assignee,
            "due_date": due_date,
            "priority": priority,
            "category": category,
            "dependencies": [],
            "estimated_effort": None,
        }

        action_items_data["action_items"].append(new_item)
        console.print("[green]✓[/green] Action item added\n")

        return action_items_data

    def dispatch_action_items(self, action_items_data: dict) -> dict:
        """Dispatch approved action items to agents.

        Args:
            action_items_data: Approved action items

        Returns:
            Dispatch results
        """
        console.print("\n[bold cyan]Step 4: Dispatching to Agents[/bold cyan]\n")

        with console.status("[bold green]Dispatching action items to agents..."):
            try:
                result = self._post_with_retry(
                    "/dispatch", {"action_items": action_items_data}, timeout=180.0
                )

                console.print(
                    "[green]✓[/green] Action items dispatched successfully!\n"
                )
                return result

            except (
                httpx.HTTPStatusError,
                httpx.TimeoutException,
                httpx.NetworkError,
            ) as e:
                console.print(f"[red]Error dispatching action items: {e}[/red]")
                console.print(
                    "[yellow]Please check that the server is running "
                    "and try again.[/yellow]"
                )
                sys.exit(1)
            except Exception as e:
                console.print(f"[red]Unexpected error: {e}[/red]")
                sys.exit(1)

    def display_results(self, results: dict):
        """Display dispatch results.

        Args:
            results: Dispatch results
        """
        console.print()
        console.print(
            "[bold cyan]═══════════════════════════════════════════════[/bold cyan]"
        )
        console.print("[bold cyan]    Execution Results[/bold cyan]")
        console.print(
            "[bold cyan]═══════════════════════════════════════════════[/bold cyan]"
        )
        console.print()

        execution_results = results.get("results", [])

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=4)
        table.add_column("Action Item", style="yellow", width=30)
        table.add_column("Agent", style="cyan", width=20)
        table.add_column("Status", width=15)
        table.add_column("Agent Response", style="white", width=120)

        for idx, result in enumerate(execution_results, 1):
            # Determine operation success: no request error and no agent error
            request_error = result.get("request_error", False)
            agent_error = result.get("agent_error", False)
            operation_success = not request_error and not agent_error

            status = (
                "[green]Success[/green]" if operation_success else "[red]Failed[/red]"
            )

            # Build response content from result
            response_parts = []

            # Add main response
            if result.get("response"):
                response_parts.append(result.get("response"))

            # Add additional info required flag if set
            if result.get("additional_info_required"):
                response_parts.append("[yellow]Additional info required[/yellow]")

            response_text = " | ".join(response_parts) if response_parts else "N/A"

            # Extract action item title
            action_item = result.get("action_item", {})
            action_item_title = (
                action_item.get("title", "N/A")
                if isinstance(action_item, dict)
                else "N/A"
            )

            # Truncate title if too long
            if len(action_item_title) > 30:
                action_item_title = action_item_title[:27] + "..."

            # Don't truncate - show full response
            table.add_row(
                str(idx),
                action_item_title,
                result.get("agent_name", "N/A"),
                status,
                response_text,
            )

        console.print(table)
        console.print()

        # Count successes based on request_error and agent_error
        successful = sum(
            1
            for r in execution_results
            if not r.get("request_error", False) and not r.get("agent_error", False)
        )
        total = len(execution_results)

        console.print(
            f"[bold]Summary: [green]{successful}/{total}[/green] "
            "operations successful[/bold]"
        )
        console.print()

    def run(self):
        """Run the interactive chat client."""
        self.display_welcome()

        meeting, date = self.get_meeting_info()
        action_items_response = self.generate_action_items(meeting, date)
        approved_action_items = self.review_and_edit_loop(action_items_response)
        dispatch_results = self.dispatch_action_items(approved_action_items)
        self.display_results(dispatch_results)

        console.print("[bold green]✓ Workflow completed successfully![/bold green]\n")


def main():
    """Main entry point for the client."""

    parser = argparse.ArgumentParser(description="Simple CLI for Action Items Workflow")
    parser.add_argument(
        "--url",
        default="http://localhost:8002",
        help="Base URL of the action items server (default: http://localhost:8002)",
    )

    args = parser.parse_args()

    client = ActionItemsSimpleClient(base_url=args.url)
    client.run()


if __name__ == "__main__":
    main()
