#!/usr/bin/env python3
"""
Opening Bell - Daily Stock Digest Generator
Fetches stock data, generates AI summaries, and emails daily digest
"""

import sys
from fetch_data import load_users, load_watchlist, fetch_all_data
from summarize import generate_digest
from send_email import send_digest_email

def process_user(user):
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
        success = process_user(user)
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