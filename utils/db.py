"""
Utilitaires de base de données JSON pour le bot ERP.
Gère les profils utilisateurs, l'historique des RP, et les personnages.
"""
import json
import os
from datetime import datetime


class JSONDatabase:
    """Gestionnaire générique de base de données JSON."""

    def __init__(self, filename: str):
        self.filename = filename
        self._ensure_exists()

    def _ensure_exists(self):
        if not os.path.exists(self.filename):
            self.save({})

    def load(self) -> dict:
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def save(self, data: dict):
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default=None):
        data = self.load()
        return data.get(str(key), default)

    def set(self, key: str, value):
        data = self.load()
        data[str(key)] = value
        self.save(data)

    def delete(self, key: str):
        data = self.load()
        if str(key) in data:
            del data[str(key)]
            self.save(data)


class ProfilesDB(JSONDatabase):
    """Gestion des profils utilisateurs avec système d'abonnement."""

    def get_profile(self, user_id: int) -> dict:
        default = {
            "name": None,
            "age": None,
            "description": None,
            "sub_type": "free",  # free, standard, premium
            "credits": 0,
            "daily_msgs_used": 0,
            "daily_sessions_used": 0,
            "last_reset": datetime.now().strftime("%Y-%m-%d"),
        }
        profile = self.get(str(user_id), default)
        for k, v in default.items():
            if k not in profile:
                profile[k] = v
        return profile

    def update_profile(self, user_id: int, **kwargs):
        profile = self.get_profile(user_id)
        profile.update(kwargs)
        self.set(str(user_id), profile)
        return profile

    def get_sub_type(self, user_id: int) -> str:
        """Retourne le type d'abonnement (free/standard/premium)."""
        profile = self.get_profile(user_id)
        return profile.get("sub_type", "free")

    def is_premium(self, user_id: int) -> bool:
        """Vérifie si l'utilisateur a au moins l'abonnement standard."""
        return self.get_sub_type(user_id) in ["standard", "premium"]

    def is_premium_plus(self, user_id: int) -> bool:
        """Vérifie si l'utilisateur a l'abonnement premium."""
        return self.get_sub_type(user_id) == "premium"

    def _check_reset_daily(self, profile: dict) -> dict:
        """Remet à zéro les compteurs quotidiens si on change de jour."""
        today = datetime.now().strftime("%Y-%m-%d")
        if profile.get("last_reset") != today:
            profile["daily_msgs_used"] = 0
            profile["daily_sessions_used"] = 0
            profile["last_reset"] = today
        return profile

    def can_send_message(self, user_id: int, max_daily: int) -> bool:
        """Vérifie si l'utilisateur peut envoyer un message (limite quotidienne)."""
        profile = self.get_profile(user_id)
        profile = self._check_reset_daily(profile)
        self.set(str(user_id), profile)
        if max_daily == -1:  # unlimited
            return True
        return profile["daily_msgs_used"] < max_daily

    def increment_messages(self, user_id: int):
        """Incrémente le compteur de messages quotidiens."""
        profile = self.get_profile(user_id)
        profile = self._check_reset_daily(profile)
        profile["daily_msgs_used"] += 1
        self.set(str(user_id), profile)

    def can_start_session(self, user_id: int, max_daily: int) -> bool:
        """Vérifie si l'utilisateur peut commencer une nouvelle séance."""
        profile = self.get_profile(user_id)
        profile = self._check_reset_daily(profile)
        self.set(str(user_id), profile)
        if max_daily == -1:
            return True
        return profile["daily_sessions_used"] < max_daily

    def increment_sessions(self, user_id: int):
        """Incrémente le compteur de séances quotidiennes."""
        profile = self.get_profile(user_id)
        profile = self._check_reset_daily(profile)
        profile["daily_sessions_used"] += 1
        self.set(str(user_id), profile)

    def get_limits(self, user_id: int) -> dict:
        """Retourne les limites selon l'abonnement."""
        sub_type = self.get_sub_type(user_id)
        from config import (
            FREE_DAILY_MSGS, FREE_DAILY_SESSIONS, FREE_MAX_TOKENS, FREE_CONTEXT, FREE_CUSTOM_CHARS,
            STANDARD_PRICE, STANDARD_DAILY_MSGS, STANDARD_DAILY_SESSIONS, STANDARD_MAX_TOKENS, STANDARD_CONTEXT, STANDARD_CUSTOM_CHARS,
            PREMIUM_PRICE, PREMIUM_DAILY_MSGS, PREMIUM_DAILY_SESSIONS, PREMIUM_MAX_TOKENS, PREMIUM_CONTEXT, PREMIUM_CUSTOM_CHARS
        )
        if sub_type == "premium":
            return {
                "daily_msgs": PREMIUM_DAILY_MSGS,
                "daily_sessions": PREMIUM_DAILY_SESSIONS,
                "max_tokens": PREMIUM_MAX_TOKENS,
                "context": PREMIUM_CONTEXT,
                "custom_chars": PREMIUM_CUSTOM_CHARS,
                "price": PREMIUM_PRICE,
                "type": "premium"
            }
        elif sub_type == "standard":
            return {
                "daily_msgs": STANDARD_DAILY_MSGS,
                "daily_sessions": STANDARD_DAILY_SESSIONS,
                "max_tokens": STANDARD_MAX_TOKENS,
                "context": STANDARD_CONTEXT,
                "custom_chars": STANDARD_CUSTOM_CHARS,
                "price": STANDARD_PRICE,
                "type": "standard"
            }
        else:
            return {
                "daily_msgs": FREE_DAILY_MSGS,
                "daily_sessions": FREE_DAILY_SESSIONS,
                "max_tokens": FREE_MAX_TOKENS,
                "context": FREE_CONTEXT,
                "custom_chars": FREE_CUSTOM_CHARS,
                "price": 0,
                "type": "free"
            }


class HistoryDB(JSONDatabase):
    """Gestion de l'historique des sessions ERP."""

    def get_session(self, user_id: int) -> dict | None:
        data = self.load()
        return data.get(str(user_id))

    def set_session(self, user_id: int, session: dict):
        data = self.load()
        data[str(user_id)] = session
        self.save(data)

    def delete_session(self, user_id: int):
        self.delete(str(user_id))

    def has_active_session(self, user_id: int) -> bool:
        return self.get_session(user_id) is not None
