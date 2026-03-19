#!/usr/bin/env python3
"""
Opening Bell - Daily Stock Digest Generator
Fetches stock data, generates AI summaries, and emails daily digest
"""

import os
import sys
from fetch_data import load_users, load_watchlist, fetch_all_data
from summarize import generate_digest
from send_email import send_digest_email
from thesis.thesis_agent import ThesisAgent

THESES_DIR = os.path.join(os.path.dirname(__file__), '..', 'theses')
THESES_TEST_DIR = os.path.join(THESES_DIR, 'test')

def _run_thesis_analysis(symbols, stocks_data_by_symbol, theses_dir, verbose=False):
    """
    Run thesis analysis for any symbol that has a thesis file in theses_dir.
    Returns a list of ThesisUpdate results.
    """
    agent = ThesisAgent()
    results = []
    for symbol in symbols:
        thesis_path = os.path.join(theses_dir, f"{symbol.upper()}.md")
        if not os.path.exists(thesis_path):
            if verbose:
                print(f"  [thesis] No thesis file for {symbol} in {theses_dir} — skipping")
            continue

        if verbose:
            print(f"  [thesis] Loaded thesis for {symbol} from {thesis_path}")

        stock = stocks_data_by_symbol.get(symbol.upper(), {})
        try:
            update = agent.analyze(
                symbol,
                news=stock.get('news'),
                earnings=stock.get('earnings'),
                theses_dir=theses_dir,
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
    """Process a single user's digest"""
    name = user.get('name', 'Unknown')
    email = user.get('email')
    symbols = user.get('symbols', [])
    
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

    # Run thesis analysis for any symbols that have a thesis file
    theses_dir = THESES_TEST_DIR if test_mode else THESES_DIR
    stocks_by_symbol = {s['symbol'].upper(): s for s in stocks_data}
    print("📋 Running thesis analysis...")
    thesis_updates = _run_thesis_analysis(
        symbols, stocks_by_symbol, theses_dir, verbose=test_mode
    )
    if thesis_updates:
        digest += "\n\n" + _build_thesis_section(thesis_updates)
        print(f"✓ Thesis Watch section added ({len(thesis_updates)} ticker(s))")
    else:
        print("  No thesis files matched — skipping Thesis Watch section")

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
    users_file = 'data/users_test.json' if test_mode else 'data/users.json'
    
    if test_mode:
        print("🧪 Running in TEST MODE")
        print(f"   Using {users_file}")
        print()
    
    # Load all users
    print("👥 Loading users...")
    users = load_users(filepath=users_file)
    
    if not users:
        print("❌ No users found in data/users.json")
        print("Falling back to single watchlist mode...")
        
        # Fallback to old single-user mode
        watchlist = load_watchlist()
        
        if not watchlist:
            print("❌ No stocks found in watchlist either. Exiting.")
            sys.exit(1)
        
        users = [{
            'name': 'Default User',
            'email': None,  # Will use RECIPIENT_EMAIL from .env
            'symbols': watchlist
        }]
    
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