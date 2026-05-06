import hashlib
import os
import re
import requests
import json
import time
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from anthropic import Anthropic

load_dotenv(find_dotenv())

# Config
OUTPUT_DIR = Path("data/reddit")
MAX_POSTS_PER_SUB = 100
MIN_BODY_LENGTH = 500

SUBREDDITS = [
    {"name": "SecurityAnalysis", "query": 'flair:"Long Thesis" OR flair:"Short Thesis" OR flair:"Thesis"'},
    {"name": "ValueInvesting",   "query": 'flair:"Stock Analysis"'},
    {"name": "Burryology",       "query": 'flair:"DD"'},
    {"name": "investing",        "query": "DD"},
    {"name": "stocks",           "query": 'flair:"Company Analysis"'},
    {"name": "ETFs",             "query": "DD"},
    {"name": "Dividends",        "query": "DD"},
]

client = Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))

HEADERS = {"User-Agent": "thesis-seeder/0.1"}

EXTRACTION_PROMPT = """You are extracting structured investment theses from Reddit posts.

A thesis can be one of three scopes:
- company: a specific long/short case on a publicly traded company or ETF
- sector: a directional view on an entire sector or industry
- macro: a macroeconomic or cross-asset view (rates, currency, commodities, geopolitics)

If this post does NOT contain a clear investment thesis of any kind, return exactly: null

Otherwise return a JSON object matching ONE of these shapes:

Company thesis:
{{
  "thesis_scope": "company",
  "ticker": "AAPL",
  "company_name": "Apple Inc.",
  "direction": "long",
  "summary": "2-3 sentence summary of the core thesis",
  "key_assumptions": ["assumption 1", "assumption 2"],
  "invalidators": ["what would prove this thesis wrong"],
  "metrics_to_monitor": ["metric 1", "metric 2"],
  "time_horizon": "e.g. 12-18 months"
}}

Sector thesis:
{{
  "thesis_scope": "sector",
  "sector": "Energy",
  "direction": "long",
  "summary": "2-3 sentence summary of the core thesis",
  "key_assumptions": ["assumption 1", "assumption 2"],
  "invalidators": ["what would prove this thesis wrong"],
  "metrics_to_monitor": ["metric 1", "metric 2"],
  "time_horizon": "e.g. 12-18 months"
}}

Macro thesis:
{{
  "thesis_scope": "macro",
  "theme": "USD weakness",
  "direction": "bearish",
  "summary": "2-3 sentence summary of the core thesis",
  "key_assumptions": ["assumption 1", "assumption 2"],
  "invalidators": ["what would prove this thesis wrong"],
  "metrics_to_monitor": ["metric 1", "metric 2"],
  "time_horizon": "e.g. 12-18 months"
}}

Return only valid JSON or null. No preamble, no markdown.

POST TITLE: {title}

POST BODY:
{body}
"""

def fetch_posts(subreddit: str, query: str) -> list[dict]:
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {"q": query, "restrict_sr": 1, "sort": "top", "t": "all", "limit": 100}

    posts = []
    after = None

    while len(posts) < MAX_POSTS_PER_SUB:
        if after:
            params["after"] = after

        resp = requests.get(url, headers=HEADERS, params=params)
        if resp.status_code != 200:
            print(f"  Request failed: {resp.status_code}")
            break

        data = resp.json()["data"]
        batch = data["children"]
        if not batch:
            break

        posts.extend([p["data"] for p in batch])
        after = data.get("after")
        if not after:
            break

        time.sleep(2)

    return posts

def extract_thesis(title: str, body: str) -> dict | None:
    prompt = EXTRACTION_PROMPT.format(title=title, body=body[:4000])

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    if raw.lower() == "null":
        return None

    # strip markdown code fences if the model ignores the "no markdown" instruction
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw).strip()

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            parsed = parsed[0] if parsed else None
        return parsed
    except json.JSONDecodeError:
        return None

def post_hash(post_id: str) -> str:
    return hashlib.sha256(post_id.encode()).hexdigest()[:8]

def output_filename(thesis: dict, phash: str) -> str:
    scope = thesis.get("thesis_scope", "company")
    if scope == "company":
        return f"{thesis['ticker'].upper()}_{phash}_thesis.md"
    if scope == "sector":
        slug = re.sub(r"[^a-z0-9]+", "_", thesis["sector"].lower()).strip("_")
        return f"sector_{slug}_{phash}_thesis.md"
    slug = re.sub(r"[^a-z0-9]+", "_", thesis["theme"].lower()).strip("_")
    return f"macro_{slug}_{phash}_thesis.md"

def to_yaml(thesis: dict, post_url: str) -> str:
    def list_items(items):
        return "\n".join(f"  - {item}" for item in items)

    scope = thesis.get("thesis_scope", "company")

    if scope == "company":
        frontmatter = f"""ticker: {thesis['ticker']}
company: {thesis['company_name']}
thesis_scope: company
direction: {thesis.get('direction', 'long')}
time_horizon: {thesis.get('time_horizon', 'unknown')}"""
    elif scope == "sector":
        frontmatter = f"""sector: {thesis['sector']}
thesis_scope: sector
direction: {thesis.get('direction', 'long')}
time_horizon: {thesis.get('time_horizon', 'unknown')}"""
    else:
        frontmatter = f"""theme: {thesis['theme']}
thesis_scope: macro
direction: {thesis.get('direction', 'neutral')}
time_horizon: {thesis.get('time_horizon', 'unknown')}"""

    return f"""---
{frontmatter}
source: reddit
confidence: draft
source_url: {post_url}
---

## Summary
{thesis['summary']}

## Key Assumptions
{list_items(thesis['key_assumptions'])}

## Invalidators
{list_items(thesis['invalidators'])}

## Metrics to Monitor
{list_items(thesis['metrics_to_monitor'])}

## Thesis Log
"""

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    seen = set()
    saved = 0
    skipped = 0

    for sub in SUBREDDITS:
        sub_name = sub["name"]
        query = sub["query"]
        print(f"\nPulling r/{sub_name} (query: {query!r})...")
        posts = fetch_posts(sub_name, query)

        candidates = [
            p for p in posts
            if p.get("is_self") and len(p.get("selftext", "")) >= MIN_BODY_LENGTH
        ]
        print(f"  {len(posts)} fetched, {len(candidates)} candidates after filter")

        for post in candidates:
            print(f"  Processing: {post['title'][:60]}...")
            thesis = extract_thesis(post["title"], post["selftext"])

            if not thesis:
                print(f"    -> null (no thesis found)")
                skipped += 1
                continue

            phash = post_hash(post["id"])
            if phash in seen:
                print(f"    -> duplicate post: {post['id']}")
                skipped += 1
                continue

            seen.add(phash)
            post_url = f"https://reddit.com{post['permalink']}"
            yaml_content = to_yaml(thesis, post_url)
            output_path = OUTPUT_DIR / output_filename(thesis, phash)
            output_path.write_text(yaml_content)
            print(f"    -> saved: {output_path}")
            saved += 1

            time.sleep(0.5)

    print(f"\nDone. Saved: {saved}, Skipped: {skipped}")

if __name__ == "__main__":
    main()
