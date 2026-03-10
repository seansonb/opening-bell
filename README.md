# Opening Bell

Fetches stock data, generates AI-written summaries, and emails a daily digest to each user on their personal watchlist. Runs automatically on weekdays via GitHub Actions before market open.

## How it works

1. Loads users and their stock watchlists from `data/users.json`
2. Fetches price data, recent news, and earnings info for each symbol via yfinance
3. Sends all stock data to an LLM (Claude or Gemini) to generate summaries
4. Emails each user an HTML-formatted digest with a market overview and per-stock analysis

## Prerequisites

- Python 3.12+
- One of the following API keys:
  - **Anthropic** (`CLAUDE_API_KEY`) — for Claude (no rate limiting needed)
  - **Google Gemini** (`GEMINI_API_KEY`) — for Gemini (free tier supported)
- A Gmail account with an [App Password](https://support.google.com/accounts/answer/185833) enabled for SMTP

## Setup

```bash
git clone https://github.com/your-username/opening-bell.git
cd opening-bell

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
# LLM provider: "claude" or "gemini"
LLM_PROVIDER=claude

# API keys (only the one matching LLM_PROVIDER is required)
CLAUDE_API_KEY=your_anthropic_api_key
GEMINI_API_KEY=your_gemini_api_key

# Gmail sender credentials
SENDER_EMAIL=you@gmail.com
SENDER_PASSWORD=your_gmail_app_password

# Fallback recipient if a user has no email set
RECIPIENT_EMAIL=you@gmail.com
```

## Configuration

### LLM Provider

Set `LLM_PROVIDER` in `.env` to switch between models:

| Value | Model | Notes |
|-------|-------|-------|
| `claude` | Claude Sonnet (Anthropic) | Processes stocks individually, no rate limiting |
| `gemini` | Gemini Flash (Google) | Batches up to 10 stocks per request, rate limited |

### User watchlists — `data/users.json`

Each user has a `name`, `email`, and list of ticker `symbols`. Each user gets their own digest email.

```json
{
  "users": [
    {
      "name": "Alice",
      "email": "alice@example.com",
      "symbols": ["AAPL", "NVDA", "MSFT"]
    }
  ]
}
```

### Fallback watchlist — `data/watchlist.json`

Used as a fallback if `users.json` is missing or empty. Sends a single digest to `RECIPIENT_EMAIL`.

```json
{
  "symbols": ["AAPL", "NVDA", "MSFT"]
}
```

### Test users — `data/users_test.json`

A separate users file for test runs. Same format as `users.json`.

## Running locally

Full run (all users in `data/users.json`):

```bash
cd src
python main.py
```

Test run (uses `data/users_test.json` instead):

```bash
python main.py --test
# or
python main.py -t
```

## GitHub Actions

The workflow at `.github/workflows/daily-digest.yml` runs `python src/main.py` Monday–Friday at 9:00 AM ET (14:00 UTC). It can also be triggered manually from the Actions tab.

### Required repository secrets

Set these under **Settings → Secrets and variables → Actions**:

| Secret | Description |
|--------|-------------|
| `GEMINI_API_KEY` | Gemini API key (or swap for `CLAUDE_API_KEY` and update the workflow) |
| `SENDER_EMAIL` | Gmail address to send from |
| `SENDER_PASSWORD` | Gmail App Password |

On failure, logs are uploaded as a workflow artifact for debugging.
