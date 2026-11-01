"""Bithumb private-account READ-ONLY client. Never submits orders.

Environment variables: BITHUMB_ACCESS_KEY and BITHUMB_SECRET_KEY.
Do not expose raw API responses or credentials to public endpoints.
"""
import base64
import hashlib
import hmac
import json
import os
import time
import uuid
import urllib.request
from decimal import Decimal, InvalidOperation

BASE = "https://api.bithumb.com"

class AccountError(Exception):
    pass

def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

def _jwt(access_key, secret_key, nonce=None, timestamp_ms=None):
    if not access_key or not secret_key:
        raise AccountError("Read-only account keys are not configured")
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"access_key": access_key, "nonce": nonce or str(uuid.uuid4()),
               "timestamp": int(timestamp_ms if timestamp_ms is not None else time.time() * 1000)}
    signing_input = ".".join((_b64(json.dumps(header, separators=(",", ":")).encode()),
                              _b64(json.dumps(payload, separators=(",", ":")).encode())))
    signature = hmac.new(secret_key.encode(), signing_input.encode(), hashlib.sha256).digest()
    return signing_input + "." + _b64(signature)

def _decimal(value):
    try:
        n = Decimal(str(value))
        if not n.is_finite() or n < 0:
            raise ValueError("Invalid account amount")
        return n
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AccountError("Invalid account numeric field") from exc

def normalize_balances(rows):
    """Return only necessary fields; no API keys, UUIDs, or personal details."""
    if not isinstance(rows, list):
        raise AccountError("Unexpected balances response")
    output = []
    for row in rows:
        if not isinstance(row, dict):
            raise AccountError("Unexpected balance item")
        currency = row.get("currency")
        if not isinstance(currency, str) or not currency.isalnum() or len(currency) > 15:
            raise AccountError("Invalid currency")
        free = _decimal(row.get("balance"))
        locked = _decimal(row.get("locked"))
        avg = _decimal(row.get("avg_buy_price"))
        output.append({"currency": currency.upper(), "available": str(free),
                       "locked": str(locked), "total": str(free + locked),
                       "avg_buy_price": str(avg)})
    return output

def read_balances(access_key=None, secret_key=None, opener=None):
    access_key = access_key if access_key is not None else os.getenv("BITHUMB_ACCESS_KEY", "")
    secret_key = secret_key if secret_key is not None else os.getenv("BITHUMB_SECRET_KEY", "")
    if not access_key or not secret_key:
        return {"connected": False, "balances": [], "reason": "API credentials not configured"}
    request = urllib.request.Request(BASE + "/v1/accounts",
        headers={"Authorization": "Bearer " + _jwt(access_key, secret_key),
                 "Accept": "application/json", "User-Agent": "MY-SIGNAL-READONLY/1.0"},
        method="GET")
    try:
        with (opener or urllib.request.urlopen)(request, timeout=10) as response:
            rows = json.load(response)
        return {"connected": True, "balances": normalize_balances(rows),
                "observed_at": int(time.time())}
    except Exception as exc:
        # Never surface server-returned text: it may contain sensitive data.
        raise AccountError("Bithumb read-only account request failed") from exc
