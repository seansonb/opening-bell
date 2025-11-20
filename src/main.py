#!/usr/bin/env python3
"""
Opening Bell - Daily Stock Digest Generator
Fetches stock data, generates AI summaries, and emails daily digest
"""

import sys
from fetch_data import load_watchlist, fetch_all_data
from summarize import generate_digest
from send_email import send_digest_email

def main():
    """Main function to orchestrate the daily digest generation"""
    
    print("=" * 60)
    print("Opening Bell - Daily Stock Digest")
    print("=" * 60)
    print()
    
    # Step 1: Load watchlist
    print("📋 Loading watchlist...")
    watchlist = load_watchlist()
    
    if not watchlist:
        print("❌ No stocks found in watchlist. Please add stocks to data/watchlist.json")
        sys.exit(1)
    
    print(f"✓ Loaded {len(watchlist)} stocks: {', '.join(watchlist)}")
    print()
    
    # Step 2: Fetch stock data
    print("📊 Fetching stock data and news...")
    stocks_data = fetch_all_data(watchlist)
    
    if not stocks_data:
        print("❌ Failed to fetch any stock data")
        sys.exit(1)
    
    print(f"✓ Successfully fetched data for {len(stocks_data)} stocks")
    print()
    
    # Step 3: Generate AI summaries
    print("🤖 Generating AI summaries with Gemini...")
    digest = generate_digest(stocks_data)
    print("✓ Digest generated successfully")
    print()
    
    # Step 4: Send email
    print("📧 Sending email digest...")
    success = send_digest_email(digest)
    
    if success:
        print()
        print("=" * 60)
        print("✅ Daily digest completed successfully!")
        print("=" * 60)
    else:
        print()
        print("=" * 60)
        print("⚠️  Digest generated but email failed to send")
        print("=" * 60)
        print("\nDigest preview:")
        print(digest[:500] + "...")
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