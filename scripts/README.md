# Scripts Directory

This directory contains helper scripts for the Agents project.

## generate_token.py

Generates `token.json` for Google OAuth authentication used by the google-mcp container.

### Purpose

The Google MCP container requires OAuth credentials to access Google APIs (Calendar, Docs, Gmail, Meet). Since containers cannot run an interactive browser-based OAuth flow, you must generate the `token.json` file locally first.

### Prerequisites

1. **credentials.json**: Download OAuth 2.0 credentials from Google Cloud Console
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create or select a project
   - Enable required APIs:
     - Google Calendar API
     - Google Docs API
     - Google Meet API
     - Gmail API
   - Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
   - Select "Desktop application" as the application type
   - Download the JSON file and save it as `credentials.json` in the project root

2. **Browser access**: You need a browser available to complete the OAuth flow

### Usage

```bash
# From the project root directory
python scripts/generate_token.py
```

The script automatically handles file ownership for both rootless Podman and Docker environments.

### What it does

1. Checks if `credentials.json` exists
2. Checks if `token.json` already exists and is valid
3. If token is expired but has a refresh token, attempts to refresh it
4. If no valid token exists, runs the OAuth flow:
   - Opens a browser window
   - Prompts you to log in with your Google account
   - Asks you to authorize the application
   - Saves the token to `token.json`

### Output

After successful execution, you'll have a `token.json` file in the project root directory. This file will be automatically mounted into the google-mcp container via docker-compose.yml.

### Token Refresh

The token will be automatically refreshed by the container when it expires, as long as it has a valid refresh token. If refresh fails, you'll need to regenerate the token using this script.

### Troubleshooting

**Error: credentials.json not found**
- Make sure you've downloaded OAuth credentials from Google Cloud Console
- Save the file as `credentials.json` in the project root directory

**Error: OAuth flow failed**
- Ensure the OAuth consent screen is configured in Google Cloud Console
- Verify that all required APIs are enabled
- Check that you're using the correct Google account

**Error: This script cannot be run in a container**
- This script must be run on your local machine, not inside a Docker container
- Exit the container and run it from your local terminal

### File Ownership and Permissions

The script automatically sets `token.json` permissions to `0o600` (rw-------) for security and configures the correct ownership for containers.

**For rootless Podman:**
The script automatically uses `podman unshare chown 1000:1000` to set the file ownership in the container user namespace. This allows the google-mcp container to read and write the token file when it needs to refresh the token, without requiring sudo or manual permission changes.

**How it works:**
- Rootless podman uses user namespaces to map host UIDs to container UIDs
- The script uses `podman unshare` to set ownership to UID/GID 1000:1000 in the container namespace
- On the host, the file will appear to be owned by a high UID (e.g., 166535), but inside containers it's owned by 1000:1000
- The google-mcp container can seamlessly read/write the token

**For Docker:**
The script will notify you if podman is not available. You may need to manually set ownership:
```bash
sudo chown 1000:1000 token.json
```

### Security Notes

- `token.json` contains sensitive OAuth credentials - never commit it to version control
- The file is already listed in `.gitignore`
- File permissions are set to `600` (owner read/write only) for security
- Tokens can be revoked at any time from [Google Account Security](https://myaccount.google.com/security)
