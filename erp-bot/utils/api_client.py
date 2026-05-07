"""API Client for KlaraAI Credits API"""
import json
import os
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

API_BASE = os.getenv("API_BASE", "http://localhost:3000")
API_SECRET = os.getenv("API_SECRET", "")

def get_credits(discord_id):
    url = API_BASE + "/api/credits?discord_id=" + str(discord_id)
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print("[API] Error: " + str(e))
        return {"discord_id": discord_id, "username": "Unknown", "credits": 0}

def add_credits(discord_id, amount, username, pack_name="Bot Gift"):
    url = API_BASE + "/api/credits/add"
    body = {"discord_id": discord_id, "amount": amount, "pack_name": pack_name, "username": username, "secret": API_SECRET}
    try:
        req = Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        error_body = e.read().decode("utf-8")
        print("[API] HTTP Error: " + str(e.code) + " - " + error_body)
        return {"success": False, "error": "HTTP " + str(e.code)}
    except Exception as e:
        print("[API] Error: " + str(e))
        return {"success": False, "error": str(e)}


def set_referrer(referred_id, referrer_id):
    """Tell the API to remember this referral so the webhook can reward the referrer on first purchase."""
    url = API_BASE + "/api/referrals/set"
    body = {"referred_id": str(referred_id), "referrer_id": str(referrer_id), "secret": API_SECRET}
    try:
        req = Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST")
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        try:
            error_body = e.read().decode("utf-8")
        except Exception:
            error_body = ""
        print("[API] referrals/set HTTP " + str(e.code) + " - " + error_body)
        return {"success": False, "error": "HTTP " + str(e.code)}
    except Exception as e:
        print("[API] referrals/set error: " + str(e))
        return {"success": False, "error": str(e)}