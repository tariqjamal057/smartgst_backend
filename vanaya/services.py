"""Base API handler for the Vanaya (GSTN GSP) gateway.

Crypto is delegated to the known-working Java helpers under ``vanaya_api/``
(compiled into ``.class`` files and invoked as CLI scripts, see
``vanaya.crypto``). Python handles HTTP, signing orchestration and caching.

Two calling approaches are supported:

* **Explicit**: when ``gstin``, ``username``, ``ip_usr`` and ``cust_id`` are
  all provided (``from_data``), the request uses exactly those values.
* **Default**: otherwise (or via ``from_defaults``) the client falls back to
  the env-configured defaults.

Auth state is cached per GSTIN using two tiers:

* **Temp** (``tmp:``-prefixed keys): the raw/encrypted ``app_key`` for the
  in-flight OTP flow (send_otp -> authenticate). ``send_otp`` always
  regenerates it (a resent OTP discards the previous attempt) and it expires
  after ``VANAYA_OTP_TEMP_TTL_SECONDS``.
* **Permanent**: ``auth_token``, ``expiry``, decrypted ``dek``, raw/encrypted
  ``app_key`` and the raw auth response, promoted on successful verification
  with a TTL of ``expiry`` minutes (``VANAYA_AUTH_TOKEN_TTL_MINUTES`` default).
"""

import json
import secrets
from datetime import datetime, timedelta, timezone

import requests
from django.conf import settings
from django.core.cache import cache
from rest_framework import status as http_status

from . import crypto

#: GSTN/Vayana well-known relative endpoints (from the Postman collection).
AUTHENTICATE_PATH = "/gus/taxpayerapi/v1.0/authenticate"
SEARCH_PATH = "/gus/commonapi/v1.3/search"
RETURNS_PATH = "/gus/taxpayerapi/v1.0/returns"

#: Signed-only "public" GSTN APIs. No OTP session token is required (only the
#: X-Asp-Auth-Token/Signature headers) and their ``data`` field carries plain
#: base64-encoded JSON instead of the two-step AES-encrypted payload.
PUBLIC_PATHS = (SEARCH_PATH,)

#: IST is UTC+05:30 (India does not observe DST).
IST_OFFSET = timedelta(hours=5, minutes=30)

#: Default action name used by profile/search calls.
ACTION_SEARCH = "TP"

#: Credentials that opt out of all four override the session defaults.
OVERRIDABLE_FIELDS = ("gstin", "username", "ip_usr", "cust_id")

#: Fallback session lifetime (minutes) when the AUTHTOKEN response omits
#: ``expiry`` (the gateway usually returns it, e.g. 360).
DEFAULT_AUTH_TOKEN_TTL_MINUTES = 360


class VanayaError(Exception):
    """Raised when the Vanaya gateway returns a non-success status code."""

    def __init__(self, message, error_cd=None, status_code=http_status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.error_cd = error_cd
        self.status_code = status_code
        super().__init__(message)


def _now_ist() -> datetime:
    return datetime.now(timezone.utc) + IST_OFFSET


def _fmt_timestamp(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H%M%S") + "+0530"


class VanayaClient:
    """Thread-safe per-call base handler for the Vanaya GST gateway."""

    def __init__(
        self,
        gstin=None,
        username=None,
        cust_id=None,
        state_code=None,
        ip_usr=None,
        base_url=None,
        private_key_path=None,
        public_key_path=None,
        key_password=None,
        java_source_dir=None,
        java_class_dir=None,
        timeout=None,
    ):
        # Explicit-only approach (from_data) always provides all four; defaults
        # kick in for anything missing, so callers may override selectively too.
        self.gstin = gstin or settings.VANAYA_GSTIN
        self.username = username or settings.VANAYA_USERNAME
        self.cust_id = cust_id or settings.VANAYA_CUST_ID
        self.state_code = state_code or settings.VANAYA_STATE_CODE
        self.ip_usr = ip_usr or settings.VANAYA_IP_USR
        self.base_url = (base_url or settings.VANAYA_BASE_URL).rstrip("/")
        self.private_key_path = private_key_path or settings.VANAYA_PRIVATE_KEY_PATH
        self.public_key_path = public_key_path or settings.VANAYA_PUBLIC_KEY_PATH
        self.key_password = (
            key_password if key_password is not None else settings.VANAYA_KEY_PASSWORD
        )
        self.java_source_dir = java_source_dir or settings.VANAYA_JAVA_SOURCE_DIR
        self.java_class_dir = java_class_dir or settings.VANAYA_JAVA_CLASS_DIR
        self.timeout = timeout or settings.VANAYA_REQUEST_TIMEOUT

        if not self.private_key_path:
            raise VanayaError(
                "VANAYA_PRIVATE_KEY_PATH is not configured.",
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        if not self.public_key_path:
            raise VanayaError(
                "VANAYA_PUBLIC_KEY_PATH is not configured.",
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        self._class_dir = None

    # ------------------------------------------------------------------ #
    # Construction strategies                                            #
    # ------------------------------------------------------------------ #
    @classmethod
    def from_defaults(cls, **overrides) -> "VanayaClient":
        """Client using the env-configured defaults (optionally overridden)."""
        kwargs = {key: value for key, value in overrides.items() if value}
        if "ip" in kwargs:
            kwargs["ip_usr"] = kwargs.pop("ip")
        return cls(**kwargs)

    @classmethod
    def from_data(cls, data: dict) -> "VanayaClient":
        """Explicit-only approach.

        Uses the supplied ``gstin``/``username``/``ip``/``cust_id`` only when
        *all four* are provided; falls back to env defaults otherwise.
        """
        fields = {key: (data or {}).get(key) for key in OVERRIDABLE_FIELDS}
        if "ip_usr" not in fields or not fields["ip_usr"]:
            fields["ip_usr"] = (data or {}).get("ip")
        if all(fields.values()):
            return cls(**fields)
        return cls.from_defaults()

    @property
    def class_dir(
        self,
    ):
        """Compile (once) and return the Java class directory."""
        if self._class_dir is None:
            self._class_dir = crypto.ensure_built(self.java_source_dir, self.java_class_dir)
        return self._class_dir

    # ------------------------------------------------------------------ #
    # Cache helpers (per GSTIN)                                          #
    # ------------------------------------------------------------------ #
    def _cache_key(self, suffix: str) -> str:
        return f"vanaya:{self.gstin}:{suffix}"

    def _cache_get(self, suffix: str):
        return cache.get(self._cache_key(suffix))

    def _cache_set(self, suffix: str, value, timeout=None):
        cache.set(self._cache_key(suffix), value, timeout=timeout)

    # ------------------------------------------------------------------ #
    # Headers / signing                                                  #
    # ------------------------------------------------------------------ #
    @staticmethod
    def generate_txn_id() -> str:
        ts = datetime.now(timezone.utc) + IST_OFFSET
        return f"TXN{ts.strftime('%Y%m%d%H%M%S')}{secrets.token_hex(2).upper()}"

    def _auth_token_string(self, txn_id: str, action: str, gstin: str) -> str:
        timestamp = _fmt_timestamp(_now_ist())
        return f"v2.0:{self.cust_id}::{txn_id}:{timestamp}:{gstin}:{action}"

    def _auth_headers(self, txn_id: str, action: str, gstin: str) -> dict:
        auth_token_string = self._auth_token_string(txn_id, action, gstin)
        return {
            "cust_id": self.cust_id,
            "X-Asp-Auth-Token": auth_token_string,
            "X-Asp-Auth-Signature": crypto.sign_sha256(
                self.private_key_path,
                auth_token_string,
                self.class_dir,
                self.key_password,
            ),
            "state-cd": self.state_code,
            "ip-usr": self.ip_usr,
            "txn": txn_id,
        }

    def _authed_headers(self, txn_id: str, action: str, gstin: str) -> dict:
        """Headers for authenticated calls (adds auth-token/username/gstin)."""
        headers = self._auth_headers(txn_id, action, gstin)
        authtoken = self.get_auth_token()
        if not authtoken:
            raise VanayaError(
                "No active Vanaya session. Call send_otp/authenticate first.",
                status_code=http_status.HTTP_401_UNAUTHORIZED,
            )
        headers["auth-token"] = authtoken
        headers["username"] = self.username
        headers["gstin"] = self.gstin
        return headers

    # ------------------------------------------------------------------ #
    # App key / OTP helpers                                              #
    # ------------------------------------------------------------------ #
    def _build_app_key(self) -> str:
        return secrets.token_hex(16)

    def _store_temp_app_key(self, raw_app_key: str):
        encrypted_app_key = crypto.rsa_encrypt_app_key(
            self.public_key_path, raw_app_key, self.class_dir
        )
        timeout = settings.VANAYA_OTP_TEMP_TTL_SECONDS
        self._cache_set("tmp:app_key", raw_app_key, timeout=timeout)
        self._cache_set("tmp:app_key_enc", encrypted_app_key, timeout=timeout)

    def _load_temp_app_key(self):
        raw_app_key = self._cache_get("tmp:app_key")
        encoded_app_key = self._cache_get("tmp:app_key_enc")
        if raw_app_key is None or encoded_app_key is None:
            raise VanayaError(
                "No in-flight OTP request. Call send_otp before authenticating.",
                status_code=http_status.HTTP_401_UNAUTHORIZED,
            )
        return raw_app_key, encoded_app_key

    # ------------------------------------------------------------------ #
    # Session state                                                      #
    # ------------------------------------------------------------------ #
    def get_auth_token(self):
        return self._cache_get("auth_token")

    def has_active_session(self) -> bool:
        return bool(self.get_auth_token())

    # ------------------------------------------------------------------ #
    # HTTP plumbing                                                      #
    # ------------------------------------------------------------------ #
    def _requires_session(self, path: str) -> bool:
        """True for endpoints needing a validated OTP ``auth-token``.

        Auth endpoints (OTPREQUEST/AUTHTOKEN) and the signed-only public APIs
        (e.g. search) only need the X-Asp-* headers, so they get no session.
        """
        return path not in PUBLIC_PATHS and path != AUTHENTICATE_PATH

    def _request(
        self,
        method: str,
        path: str,
        action: str,
        params: dict | None = None,
        payload: dict | None = None,
        gstin: str | None = None,
        session_required: bool | None = None,
    ) -> dict:
        gstin = gstin or self.gstin
        txn_id = self.generate_txn_id()
        url = f"{self.base_url}{path}"

        if session_required is None:
            session_required = self._requires_session(path)

        headers = (
            self._authed_headers(txn_id, action, gstin)
            if session_required
            else self._auth_headers(txn_id, action, gstin)
        )

        try:
            if method.lower() == "get":
                response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
            else:
                response = requests.post(
                    url, json=payload or {}, headers=headers, timeout=self.timeout
                )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise VanayaError(
                f"Vanaya gateway request failed: {exc}",
                status_code=http_status.HTTP_502_BAD_GATEWAY,
            ) from exc

        try:
            body = response.json()
        except ValueError as exc:
            raise VanayaError(
                "Invalid JSON received from Vanaya gateway.",
                status_code=http_status.HTTP_502_BAD_GATEWAY,
            ) from exc

        if body.get("status_cd") not in ("1", 1):
            error = body.get("error", {}) or {}
            raise VanayaError(
                error.get("message", body.get("error_cd") or "Unknown Vanaya error"),
                error_cd=error.get("error_cd", body.get("error_cd")),
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return body

    def _decrypt_response(self, body: dict, *, public: bool = False) -> dict:
        """Decrypt the payload according to the response type.

        * ``public=True`` -> public API response: ``data`` is plain base64-
          encoded JSON, so we only base64-decode it (no ``dek`` needed).
        * ``public=False`` -> authenticated API response: ``data``/``rek`` are
          AES-encrypted and need the two-step GSTN decryption with the raw key
          (``dek`` stored from the auth flow).
        """
        result = dict(body)
        data = body.get("data")
        if not data:
            return result

        if public or not body.get("rek"):
            # Plain base64 payload (either a public API or an authed endpoint
            # that did not encrypt the data field).
            result["data"] = crypto.decrypt_search_data(data)
            return result

        dek = self._cache_get("dek")
        if dek is None:
            raise VanayaError(
                "Missing decryption key for Vanaya payload.",
                status_code=http_status.HTTP_401_UNAUTHORIZED,
            )
        result["data"] = crypto.decrypt_api_response(dek, body["rek"], data, self.class_dir)
        try:
            result["data"] = json.loads(result["data"])
        except (ValueError, TypeError):
            pass
        return result

    # ------------------------------------------------------------------ #
    # Auth API                                                           #
    # ------------------------------------------------------------------ #
    def send_otp(self) -> dict:
        """Send OTPREQUEST using a fresh random app key.

        Any previous (failed or re-issued) request is discarded: a new raw
        app key is always generated and stored in the temp tier until the
        OTP is verified via :meth:`authenticate`.
        """
        cache.delete(self._cache_key("tmp:app_key"))
        self._store_temp_app_key(self._build_app_key())
        encoded_app_key = self._cache_get("tmp:app_key_enc")

        payload = {
            "action": "OTPREQUEST",
            "username": self.username,
            "app_key": encoded_app_key,
        }
        return self._request("post", AUTHENTICATE_PATH, "OTPREQUEST", payload=payload)

    def authenticate(self, otp: str | None = None, username: str | None = None) -> dict:
        """Complete the auth flow (AUTHTOKEN).

        ``otp`` is optional: when omitted (or empty) the configured
        ``VANAYA_DEFAULT_OTP`` is used, mirroring the Java helper's fixed
        sandbox OTP behaviour.

        Requires a pending ``send_otp`` (temp app key). On success the temp
        app key is promoted to a permanent cache entry together with the
        ``auth_token``, ``expiry`` and decrypted ``sek``, all valid for
        ``expiry`` minutes so subsequent authenticated calls can reuse them.
        """
        raw_app_key, encoded_app_key = self._load_temp_app_key()
        otp = otp or settings.VANAYA_DEFAULT_OTP

        otp_enc = crypto.encrypt_otp(
            self.public_key_path, raw_app_key, otp, self.class_dir, self.username
        )
        payload = {
            "action": "AUTHTOKEN",
            "username": username or self.username,
            "app_key": encoded_app_key,
            "otp": otp_enc,
        }
        body = self._request("post", AUTHENTICATE_PATH, "AUTHTOKEN", payload=payload)

        expiry_minutes = body.get("expiry") or settings.VANAYA_AUTH_TOKEN_TTL_MINUTES
        timeout = int(expiry_minutes) * 60

        # Decrypt and remember the SEK (payload decryption key).
        dek = crypto.decrypt_sek(raw_app_key, body["sek"], self.class_dir)
        self._cache_set("dek", dek, timeout=timeout)
        self._cache_set("auth_token", body["auth_token"], timeout=timeout)
        self._cache_set("expiry", expiry_minutes, timeout=timeout)
        # Store the raw auth response (per requirements) for audits/debug.
        self._cache_set("auth_response", body, timeout=timeout)
        # Promote the app key to the permanent tier for the session lifetime.
        self._cache_set("app_key", raw_app_key, timeout=timeout)
        self._cache_set("app_key_enc", encoded_app_key, timeout=timeout)

        # The temp key pair is consumed by a successful verification.
        cache.delete(self._cache_key("tmp:app_key"))
        cache.delete(self._cache_key("tmp:app_key_enc"))

        result = dict(body)
        result["dek"] = dek
        result["app_key"] = raw_app_key
        return result

    # ------------------------------------------------------------------ #
    # Generic GET / POST for all other endpoints                         #
    # ------------------------------------------------------------------ #
    def get(self, path: str, action: str, params: dict | None = None) -> dict:
        """Authenticated GET for session-protected endpoints."""
        return self._decrypt_response(self._request("get", path, action, params=params))

    def get_public(self, path: str, action: str, params: dict | None = None) -> dict:
        """Signed-only GET for the public GSP endpoints (e.g. search)."""
        return self._decrypt_response(
            self._request("get", path, action, params=params),
            public=True,
        )

    def post(self, path: str, action: str, payload: dict | None = None) -> dict:
        """Authenticated POST (non-auth actions go straight through)."""
        return self._decrypt_response(self._request("post", path, action, payload=payload or {}))

    # ------------------------------------------------------------------ #
    # Postman mirror helpers                                             #
    # ------------------------------------------------------------------ #
    def search_gstin(self, search_gstin: str | None = None) -> dict:
        """Get GSTN info (``/gus/commonapi/v1.3/search``, action TP).

        Public endpoint: signed headers only, ``data`` is base64-decode only.
        """
        return self.get_public(
            SEARCH_PATH,
            ACTION_SEARCH,
            params={"action": ACTION_SEARCH, "gstin": search_gstin or self.gstin},
        )

    def get_returns(self, action: str, **params) -> dict:
        """Fetch returns (``/gus/taxpayerapi/v1.0/returns``)."""
        params = dict(params)
        params.setdefault("action", action)
        params.setdefault("gstin", self.gstin)
        return self.get(RETURNS_PATH, params["action"], params=params)

    def clear_session(self):
        for suffix in (
            "app_key",
            "app_key_enc",
            "dek",
            "auth_token",
            "expiry",
            "auth_response",
            "tmp:app_key",
            "tmp:app_key_enc",
        ):
            cache.delete(self._cache_key(suffix))
