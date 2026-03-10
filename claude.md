# Opening Bell - Claude Code Instructions

## Workflow
- Always read relevant files before proposing changes
- Always show a plan and wait for explicit approval before editing any files
- Make changes incrementally - don't rewrite everything at once

## Project Structure
- src/ - all source code
- data/ - watchlist and user config JSON files
- .env - API keys (never modify this file)

## Rules
- Never modify main.py, send_email.py, or any files in data/ unless explicitly asked
- Never commit or suggest committing .env
- When adding dependencies, always update requirements.txt