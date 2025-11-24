#!/usr/bin/env python3
"""
Helper script to generate token.json for Google OAuth authentication.

This script runs the OAuth flow locally (which requires a browser) and generates
a token.json file that can be used in containerized environments.

Usage:
    python scripts/generate_token.py

Requirements:
    - credentials.json must exist in the project root directory
    - You must have a browser available for the OAuth flow
    - You must be running this locally (not in a container)
"""

import os
import subprocess
import sys

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# pylint: disable=wrong-import-position
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from src.integrations.google_tools.auth_utils import SCOPES

# pylint: enable=wrong-import-position


def set_token_ownership(token_path: str) -> None:
    """Set secure permissions on token.json and configure ownership for containers.

    Args:
        token_path: Path to the token.json file
    """
    try:
        os.chmod(token_path, 0o600)
        print("✓ Set secure file permissions (600 - owner read/write only)")
    except Exception as e:
        print(f"⚠ Warning: Could not set file permissions: {e}")
        return

    # Try to set ownership for container using podman unshare
    try:
        result = subprocess.run(
            ["podman", "unshare", "chown", "1000:1000", token_path],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        if result.returncode == 0:
            print("✓ Set ownership for container user namespace (1000:1000)")
            # Show ownership from both perspectives
            stat_info = os.stat(token_path)
            print(f"  Host UID/GID: {stat_info.st_uid}:{stat_info.st_gid}")
        else:
            print(
                f"⚠ Could not set ownership via podman unshare: {result.stderr.strip()}"
            )
            print("  If using Docker, you may need to manually run:")
            print(f"  sudo chown 1000:1000 {token_path}")

    except FileNotFoundError:
        print("ℹ Note: podman not found")
        print("  If using Docker and containers can't access the token, run:")
        print(f"  sudo chown 1000:1000 {token_path}")
    except subprocess.TimeoutExpired:
        print("⚠ Warning: podman unshare timed out")
    except Exception as e:
        print(f"⚠ Warning: Could not run podman unshare: {e}")


def main():  # pylint: disable=too-many-statements
    """Generate token.json using OAuth flow."""
    print("=" * 60)
    print("Google OAuth Token Generator")
    print("=" * 60)
    print()

    # Check if running in a container
    if os.getenv("RUNNING_IN_CONTAINER", "false").lower() == "true":
        print("ERROR: This script cannot be run in a container.")
        print("Please run it on your local machine where a browser is available.")
        sys.exit(1)

    # Check if credentials.json exists
    credentials_path = os.path.join(project_root, "credentials.json")
    if not os.path.exists(credentials_path):
        print(f"ERROR: credentials.json not found at {credentials_path}")
        print()
        print("Please follow these steps:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create or select a project")
        print("3. Enable the required Google APIs:")
        print("   - Google Calendar API")
        print("   - Google Docs API")
        print("   - Google Meet API")
        print("   - Gmail API")
        print("4. Create OAuth 2.0 credentials (Desktop application)")
        print("5. Download the credentials and save as credentials.json")
        print(f"6. Place credentials.json in {project_root}")
        sys.exit(1)

    token_path = os.path.join(project_root, "token.json")

    # Check if token.json already exists
    creds = None
    if os.path.exists(token_path):
        print(f"Found existing token.json at {token_path}")
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            print("Successfully loaded existing credentials.")

            # Check if credentials are valid
            if creds.valid:
                print("✓ Credentials are valid and ready to use!")
                print()
                # Ensure ownership and permissions are correct
                set_token_ownership(token_path)
                print()
                print("You can now use these credentials in your docker containers.")
                print(
                    "The token.json file will be automatically "
                    "refreshed when needed."
                )
                return

            # Try to refresh if expired
            if creds.expired and creds.refresh_token:
                print("Credentials expired. Attempting to refresh...")
                try:
                    creds.refresh(Request())
                    print("✓ Successfully refreshed credentials!")

                    # Save refreshed credentials
                    with open(token_path, "w") as token:
                        token.write(creds.to_json())

                    print(f"✓ Saved refreshed credentials to {token_path}")
                    print()
                    # Set ownership and permissions
                    set_token_ownership(token_path)
                    print()
                    print(
                        "You can now use these credentials in "
                        "your docker containers."
                    )
                    return
                except Exception as err:
                    print(f"✗ Failed to refresh credentials: {err}")
                    print("Will generate new credentials...")
        except Exception as err:
            print(f"Warning: Failed to load existing token.json: {err}")
            print("Will generate new credentials...")

    # Run OAuth flow
    print()
    print("Starting OAuth flow...")
    print("This will open a browser window for you to authorize the application.")
    print()

    try:
        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
        creds = flow.run_local_server(port=0)

        # Save the credentials
        with open(token_path, "w") as token:
            token.write(creds.to_json())

        print()
        print("=" * 60)
        print("✓ SUCCESS!")
        print("=" * 60)
        print(f"✓ Generated token.json at {token_path}")
        print()
        # Set ownership and permissions
        set_token_ownership(token_path)
        print()
        print("Next steps:")
        print("1. The token.json file has been created in your project root")
        print("2. This file will be automatically mounted in your docker containers")
        print("3. Start your containers with: docker-compose up -d google-mcp")
        print()
        print("Note: The token will be automatically refreshed when it expires")
        print("      as long as it has a valid refresh token.")

    except Exception as err:
        print()
        print("=" * 60)
        print("✗ ERROR")
        print("=" * 60)
        print(f"Failed to complete OAuth flow: {err}")
        print()
        print("Common issues:")
        print("- Make sure you have a browser available")
        print("- Check that credentials.json is valid")
        print("- Ensure the OAuth consent screen is configured")
        print("- Verify that required APIs are enabled")
        sys.exit(1)


if __name__ == "__main__":
    main()
