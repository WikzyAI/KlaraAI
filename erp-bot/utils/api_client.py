"""
API Client for KlaraAI Credits API
Communicates between the Discord bot and the website credits system.
"""

import json
import os
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# API Base URL - change to your production URL when deploying
# On Render, set API_BASE=http://localhost:10000 in environment variables
API_BASE = os.getenv("API_BASE", "http://localhost:3000")

def get_credits(discord_id: str) -> dict:
    """
    Get user credits from the API.
    Returns: { discord_id, username, credits }
    """
    url = f"{API_BASE}/api/credits?discord_id={discord_id}"
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except (URLError, HTTPError, json.JSONDecodeError) as e:
        print(f"[API] Error getting credits for {discord_id}: {e}")
        return {"discord_id": discord_id, "username": "Unknown", "credits": 0}


def add_credits(discord_id: str, amount: int, username: str, pack_name: str = "Bot Gift") -> dict:
    """
    Add credits to a user (admin operation).
    Requires API_SECRET in environment.
    Returns: { success, new_balance }
    """
    url = f"{API_BASE}/api/credits/add"
    api_secret = os.getenv("API_SECRET", "")

    payload = json.dumps({
        "discord_id": discord_id,
        "amount": amount,
        "pack_name": pack_name,
        "username": username,
        "secret": api_secret
    }).encode("utf-8")

    try:
        req = Request(url, data=payload, headers={
            "Content-Type": "application/json",
            "Accept": "application/json"
        }, method="POST")
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except (URLError, HTTPError, json.JSONDecodeError) as e:
        print(f"[API] Error adding credits for {discord_id}: {e}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    # Test
    result = get_credits("1500196432211349634")
    print("Test result:", result)
