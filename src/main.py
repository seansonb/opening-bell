#!/usr/bin/env python3
"""
Opening Bell - Daily Stock Digest Generator
Fetches stock data, generates AI summaries, and emails daily digest
"""

import os
import sys
from fetch_data import fetch_all_data
from summarize import generate_digest
from send_email import send_digest_email
from thesis.thesis_agent import ThesisAgent
from utils.debug import set_debug
from db.database import init_db, purge_old_articles
from db.queries import get_all_users, get_watchlist, get_thesis

def _run_thesis_analysis(user_id, symbols, stocks_data_by_symbol, verbose=False):
    """
    Run thesis analysis for any symbol that has a thesis in the DB for this user.
    Returns a list of ThesisUpdate results.
    """
    agent = ThesisAgent()
    results = []
    for symbol in symbols:
        thesis = get_thesis(user_id, symbol)
        if thesis is None:
            if verbose:
                print(f"  [thesis] No thesis in DB for {symbol} — skipping")
            continue

        if verbose:
            print(f"  [thesis] Found thesis in DB for {symbol}")

        stock = stocks_data_by_symbol.get(symbol.upper(), {})
        try:
            update = agent.analyze(
                symbol,
                user_id=user_id,
                news=stock.get('news'),
                earnings=stock.get('earnings'),
            )
            results.append(update)
            if verbose:
                print(f"  [thesis] {symbol} verdict: {update.verdict}")
                print(f"  [thesis] {symbol} summary: {update.summary}")
        except Exception as e:
            print(f"  [thesis] Error analyzing {symbol}: {e}")

    return results


def _build_thesis_section(updates):
    """Format thesis analysis results into a digest section string."""
    lines = ["=" * 60, "", "**Thesis Watch**", ""]
    for u in updates:
        lines.append(f"**{u.ticker}** — {u.verdict}")
        lines.append("")
        lines.append(u.summary)
        lines.append("")
        lines.append("-" * 60)
        lines.append("")
    return "\n".join(lines)


def process_user(user, test_mode=False):
    """Process a single user's digest. user is a User ORM object."""
    name = user.name
    email = user.email
    symbols = get_watchlist(user.id)

    if not email:
        print(f"⚠️  Skipping {name} - no email address")
        return False

    if not symbols:
        print(f"⚠️  Skipping {name} - no symbols in watchlist")
        return False

    print(f"\n{'='*60}")
    print(f"Processing digest for {name} ({email})")
    print(f"{'='*60}")

    # Fetch stock data
    print(f"📊 Fetching data for {len(symbols)} stocks...")
    stocks_data = fetch_all_data(symbols)

    if not stocks_data:
        print(f"❌ Failed to fetch any stock data for {name}")
        return False

    print(f"✓ Successfully fetched data for {len(stocks_data)} stocks")

    # Generate AI summaries
    print("🤖 Generating AI summaries...")
    digest = generate_digest(stocks_data, user_name=name)
    print("✓ Digest generated")

    # Run thesis analysis for any symbols with a thesis in DB
    stocks_by_symbol = {s['symbol'].upper(): s for s in stocks_data}
    print("📋 Running thesis analysis...")
    thesis_updates = _run_thesis_analysis(
        user.id, symbols, stocks_by_symbol, verbose=test_mode
    )
    if thesis_updates:
        digest += "\n\n" + _build_thesis_section(thesis_updates)
        print(f"✓ Thesis Watch section added ({len(thesis_updates)} ticker(s))")
    else:
        print("  No theses found in DB — skipping Thesis Watch section")

    # Send email
    print(f"📧 Sending email to {email}...")
    success = send_digest_email(digest, recipient_email=email)

    if success:
        print(f"✅ Digest sent successfully to {name}")
        return True
    else:
        print(f"❌ Failed to send digest to {name}")
        return False

def main():
    """Main function to orchestrate the daily digest generation for all users"""
    
    print("=" * 60)
    print("Opening Bell - Daily Stock Digest")
    print("=" * 60)
    print()
    
    # Check for test mode
    test_mode = '--test' in sys.argv or '-t' in sys.argv
    if test_mode:
        os.environ['TEST_MODE'] = 'true'

    # Check for debug mode
    if '--debug' in sys.argv:
        from datetime import date
        set_debug(True)
        print(f"🐛 Debug mode enabled — logging to logs/debug_{date.today().isoformat()}.log")

    if test_mode:
        print("🧪 Running in TEST MODE")
        print()

    # Initialize DB (creates tables + seeds users/theses)
    print("🗄️  Initializing database...")
    init_db()
    purge_old_articles()
    print("✓ Database ready")

    # Load all users from DB
    print("👥 Loading users...")
    users = get_all_users()

    if not users:
        print("❌ No users found in database. Exiting.")
        sys.exit(1)

    print(f"✓ Found {len(users)} user(s)")
    
    # Process each user
    results = []
    for user in users:
        success = process_user(user, test_mode=test_mode)
        results.append(success)
    
    # Summary
    print()
    print("=" * 60)
    successful = sum(results)
    total = len(results)
    
    if successful == total:
        print(f"✅ All {total} digest(s) completed successfully!")
    else:
        print(f"⚠️  {successful}/{total} digest(s) sent successfully")
    
    # Show rate limit stats
    from summarize import _get_provider
    provider = _get_provider()
    if hasattr(provider, 'rate_limiter'):
        stats = provider.rate_limiter.get_stats()
        print(f"\n📊 API Usage:")
        print(f"   Requests today: {stats['requests_today']}/{stats['daily_limit']}")
        print(f"   Last minute: {stats['requests_last_minute']}/{stats['per_minute_limit']}")
    
    print("=" * 60)
    
    if successful == 0:
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)