import os
import time
import threading
import requests

TENANT_ID = os.environ.get("AZURE_TENANT_ID", "")
CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET", "")
ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

AZURE_CONFIGURED = all([TENANT_ID, CLIENT_ID, CLIENT_SECRET, ENDPOINT])

TOKEN_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token" if TENANT_ID else ""
SCOPE = "https://cognitiveservices.azure.com/.default"

_lock = threading.Lock()
_token_data = {"access_token": None, "expires_at": 0}


def _fetch_token():
    resp = requests.post(TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": SCOPE,
    })
    resp.raise_for_status()
    result = resp.json()
    expires_in = int(result.get("expires_in", 3600))
    with _lock:
        _token_data["access_token"] = result["access_token"]
        _token_data["expires_at"] = time.time() + expires_in - 120
    return expires_in


def get_token():
    with _lock:
        if _token_data["access_token"] and time.time() < _token_data["expires_at"]:
            return _token_data["access_token"]
    _fetch_token()
    return _token_data["access_token"]


def _refresh_loop():
    while True:
        try:
            expires_in = _fetch_token()
            sleep_for = max(expires_in - 300, 60)
        except Exception:
            sleep_for = 30
        time.sleep(sleep_for)


def start_background_refresh():
    if not AZURE_CONFIGURED:
        return
    t = threading.Thread(target=_refresh_loop, daemon=True)
    t.start()


def get_chat_url():
    return f"{ENDPOINT}/openai/deployments/{DEPLOYMENT}/chat/completions?api-version={API_VERSION}"
