"""
API Client for KlaraAI Credits API
Communicates between the Discord bot and the website credits system.
"""

import json
import os
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

API_BASE = os.getenv("API_BASE", "http://localhost:3000")
API_SECRET = os.getenv("API_SECRET", "")

def get_credits(discord_id: str) -> dict:
    """
    Get user credits from the API.
    Returns: { discord_id, username, credits }
    """
    url = f"{API_BASE}/api/credits?discord_id={discord_id}"
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=10) as resp:
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
    payload = json.dumps({
        "discord_id": discord_id,
        "amount": amount,
        "pack_name": pack_name,
        "username": username,
        "secret": API_SECRET
    }).encode("utf-8")

    try:
        req = Request(url, data=payload, headers={
            "Content-Type": "application/json",
            "Accept": "application/json"
        }, method="POST")
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"[API] add_credits result: {data}")
            return data
    except HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"[API] HTTP Error adding credits for {discord_id}: {e.code} - {error_body}")
        return {"success": False, "error": f"HTTP {e.code}: {error_body}"}
    except (URLError, json.JSONDecodeError) as e:
        print(f"[API] Error adding credits for {discord_id}: {e}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    # Test
    result = get_credits("1500196432211349634")
    print("Test result:", result)
