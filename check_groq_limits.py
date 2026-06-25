"""
Groq API Rate Limit Monitor
Checks your current rate limit status and remaining quota.
Run: python check_groq_limits.py
"""

import os
import json
from dotenv import load_dotenv
from groq import Groq
import httpx

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY", "")
SSL_CERT = os.getenv("SSL_CERT_FILE", False)

if not API_KEY:
    print("❌ GROQ_API_KEY not found in .env file")
    exit(1)

# Store headers globally to capture from response
captured_headers = {}

def capture_response_headers(response):
    """httpx event hook to capture response headers."""
    global captured_headers
    captured_headers = dict(response.headers)

# Create custom httpx client with event hooks
_http_client = httpx.Client(
    verify=SSL_CERT,
    event_hooks={"response": [capture_response_headers]}
)

client = Groq(api_key=API_KEY, http_client=_http_client)

def check_rate_limits():
    """Make a minimal API call and extract rate limit headers."""
    global captured_headers
    try:
        print("🔍 Querying Groq API to check rate limits...\n")
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "user",
                    "content": "Hello"
                }
            ],
            temperature=0,
            max_tokens=5,  # Minimal token usage
        )
        
        # Use captured headers from event hook
        if not captured_headers:
            print("⚠️  No headers captured from response.")
            return

        print("=" * 60)
        print("📊 GROQ RATE LIMIT STATUS")
        print("=" * 60)
        
        remaining_requests = captured_headers.get("x-ratelimit-remaining-requests", "N/A")
        remaining_tokens = captured_headers.get("x-ratelimit-remaining-tokens", "N/A")
        reset_requests = captured_headers.get("x-ratelimit-reset-requests", "N/A")
        reset_tokens = captured_headers.get("x-ratelimit-reset-tokens", "N/A")
        
        print(f"✅ Requests Remaining:  {remaining_requests}")
        print(f"✅ Tokens Remaining:    {remaining_tokens}")
        print(f"⏱️  Requests Reset In:   {reset_requests}")
        print(f"⏱️  Tokens Reset In:     {reset_tokens}")
        print("=" * 60)
        
        # Color-coded warnings
        if remaining_requests != "N/A":
            try:
                req_count = int(remaining_requests)
                if req_count < 10:
                    print(f"🚨 WARNING: Only {req_count} requests remaining today!")
                elif req_count < 50:
                    print(f"⚠️  CAUTION: {req_count} requests remaining")
            except ValueError:
                pass
        
        if remaining_tokens != "N/A":
            try:
                tok_count = int(remaining_tokens)
                if tok_count < 1000:
                    print(f"🚨 WARNING: Only {tok_count} tokens remaining this minute!")
                elif tok_count < 5000:
                    print(f"⚠️  CAUTION: {tok_count} tokens remaining")
            except ValueError:
                pass

    except Exception as e:
        # Check if it's a 429 Too Many Requests error
        if "429" in str(e):
            print("🛑 RATE LIMIT HIT (429 Too Many Requests)")
            print(f"Error: {e}")
            if hasattr(e, "response") and hasattr(e.response, "headers"):
                retry_after = e.response.headers.get("retry-after", "Unknown")
                print(f"⏳ Retry after {retry_after} seconds")
        else:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_rate_limits()