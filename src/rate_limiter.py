"""
Rate limiter for API calls to respect service quotas

Because we're brokies using Gemini's free tier like true degenerates.
"""

import time
from datetime import datetime, timedelta
from collections import deque

# RATE LIMIT CONFIGURATION
# We finally caved and enabled billing because 20/day was embarrassing
# But we're keeping this rate limiter because we're not COMPLETELY financially irresponsible
REQUESTS_PER_MINUTE = 1000  # If we hit this, something has gone very wrong... or very right
REQUESTS_PER_DAY = 999999   # This would actually be absurd, and might actually bankrupt me

class RateLimiter:
    """
    Rate limiter to prevent exceeding API quotas
    
    Tracks both per-minute and per-day request limits and automatically
    waits when approaching limits. Because getting rate limited is for 
    losers who don't plan ahead.
    """
    
    def __init__(self, rpm=REQUESTS_PER_MINUTE, rpd=REQUESTS_PER_DAY):
        self.requests_per_minute = rpm
        self.requests_per_day = rpd
        self.request_times = deque()  # Track request timestamps
        self.daily_count = 0
        self.daily_reset_time = datetime.now() + timedelta(days=1)
    
    def wait_if_needed(self):
        """Wait if we're about to exceed rate limits"""
        now = datetime.now()
        
        # Reset daily counter if needed
        if now >= self.daily_reset_time:
            self.daily_count = 0
            self.daily_reset_time = now + timedelta(days=1)
        
        # Check daily limit
        if self.daily_count >= self.requests_per_day:
            wait_seconds = (self.daily_reset_time - now).total_seconds()
            print(f"⚠️  Daily rate limit reached. Waiting {wait_seconds:.0f}s until reset...")
            time.sleep(wait_seconds)
            self.daily_count = 0
            self.daily_reset_time = datetime.now() + timedelta(days=1)
        
        # Remove timestamps older than 1 minute
        one_minute_ago = now - timedelta(minutes=1)
        while self.request_times and self.request_times[0] < one_minute_ago:
            self.request_times.popleft()
        
        # Check per-minute limit (leave 1 request buffer because 429 errors are embarrassing)
        if len(self.request_times) >= self.requests_per_minute - 1:
            # Wait until oldest request is >1 minute old
            oldest = self.request_times[0]
            wait_seconds = 60 - (now - oldest).total_seconds()
            if wait_seconds > 0:
                print(f"  Rate limit: waiting {wait_seconds:.1f}s...")
                time.sleep(wait_seconds)
                # Clear old timestamps after waiting
                now = datetime.now()
                one_minute_ago = now - timedelta(minutes=1)
                while self.request_times and self.request_times[0] < one_minute_ago:
                    self.request_times.popleft()
        
        # Record this request
        self.request_times.append(now)
        self.daily_count += 1
    
    def get_stats(self):
        """Get current rate limit usage stats"""
        now = datetime.now()
        one_minute_ago = now - timedelta(minutes=1)
        
        # Count requests in last minute
        recent_requests = sum(1 for t in self.request_times if t > one_minute_ago)
        
        return {
            'requests_last_minute': recent_requests,
            'requests_today': self.daily_count,
            'daily_limit': self.requests_per_day,
            'per_minute_limit': self.requests_per_minute
        }
    
    def reset(self):
        """Reset all counters (useful for testing, or when I finally upgrade to paid tier lol)"""
        self.request_times.clear()
        self.daily_count = 0
        self.daily_reset_time = datetime.now() + timedelta(days=1)