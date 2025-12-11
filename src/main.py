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
    digest = generate_digest(stocks_data)
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
    
    # Load all users
    print("👥 Loading users...")
    users = load_users()
    
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