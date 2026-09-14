"""Read-only Webull capability probe with redacted evidence.

This module deliberately exposes no order, preview, cancel, or account-write
methods. The probe only calls account listing and market-data snapshots.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Mapping

from backend.config import load_local_env

_PRODUCTION_HOST = "api.webull.com"
_SANDBOX_HOST = "api.sandbox.webull.com"
_SUBSCRIPTION_CODES = {"MARKET_DATA_NOT_SUBSCRIBED", "NOT_SUBSCRIBED", "OPRA_NOT_SUBSCRIBED"}
_TOKEN_CODES = {"INVALID_TOKEN", "TOKEN_EXPIRED", "TOKEN_INVALID"}
_AUTH_CODES = {"INVALID_APP_KEY", "INVALID_SIGNATURE", "UNAUTHORIZED"}


class WebullConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class WebullCredentials:
    environment: str
    app_key: str = field(repr=False)
    app_secret: str = field(repr=False)
    access_token: str = field(repr=False)

    @property
    def host(self) -> str:
        if self.environment in {"production", "prod"}:
            return _PRODUCTION_HOST
        if self.environment in {"sandbox", "uat", "test"}:
            return _SANDBOX_HOST
        raise WebullConfigurationError("WEBULL_ENV must be production, prod, sandbox, uat, or test.")

    @classmethod
    def from_local_env(cls, values: Mapping[str, str] | None = None) -> "WebullCredentials":
        if values is None:
            load_local_env()
            values = os.environ
        app_key = values.get("WEBULL_APP_KEY", "").strip()
        app_secret = values.get("WEBULL_APP_SECRET", "").strip()
        token = values.get("WEBULL_ACCESS_TOKEN", "").strip()
        missing = [name for name, value in (("WEBULL_APP_KEY", app_key), ("WEBULL_APP_SECRET", app_secret), ("WEBULL_ACCESS_TOKEN", token)) if not value]
        if missing:
            raise WebullConfigurationError(f"Missing required Webull configuration: {', '.join(missing)}.")
        return cls(environment=values.get("WEBULL_ENV", "production").strip().lower(), app_key=app_key, app_secret=app_secret, access_token=token)


@dataclass(frozen=True)
class HttpRequest:
    method: str
    host: str
    path: str
    headers: Mapping[str, str]


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: Any


Transport = Callable[[HttpRequest], HttpResponse]


def _body_code(body: Any) -> str:
    if not isinstance(body, dict):
        return ""
    for key in ("code", "error_code"):
        value = body.get(key)
        if value is not None:
            return str(value).upper()
    nested = body.get("data")
    return _body_code(nested) if isinstance(nested, dict) else ""


def _shape(value: Any) -> Any:
    """Produce fixture/report evidence without retaining provider data values."""
    if isinstance(value, dict):
        return {str(key): _shape(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [_shape(value[0])] if value else []
    if value is None:
        return None
    return type(value).__name__


def _evidence_hash(body: Any) -> str:
    canonical = json.dumps(_shape(body), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class WebullClient:
    """Signed HTTP client limited to the probe's read-only endpoint allowlist."""

    def __init__(
        self,
        credentials: WebullCredentials,
        transport: Transport | None = None,
        now: Callable[[], datetime] | None = None,
        nonce: Callable[[], str] | None = None,
    ) -> None:
        self.credentials = credentials
        self._transport = transport or self._send
        self._now = now or (lambda: datetime.now(UTC))
        self._nonce = nonce or (lambda: secrets.token_hex(16))

    def get(self, path: str) -> HttpResponse:
        if path.split("?", 1)[0] not in {
            "/trading/accounts/list",
            "/market-data/stocks/snapshots/list",
            "/market-data/options/snapshots/list",
        }:
            raise ValueError("Webull probe attempted a non-allowlisted endpoint.")
        return self._transport(self._signed_request(path))

    def _signed_request(self, path: str) -> HttpRequest:
        timestamp = self._now().astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        signing_headers = {
            "host": self.credentials.host,
            "x-app-key": self.credentials.app_key,
            "x-signature-algorithm": "HMAC-SHA1",
            "x-signature-nonce": self._nonce(),
            "x-signature-version": "1.0",
            "x-timestamp": timestamp,
        }
        parameter_string = "&".join(f"{key}={signing_headers[key]}" for key in sorted(signing_headers))
        signing_input = urllib.parse.quote(f"{path}&{parameter_string}", safe="~()*!.'-_")
        signature = base64.b64encode(hmac.new(f"{self.credentials.app_secret}&".encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha1).digest()).decode("ascii")
        return HttpRequest(
            method="GET",
            host=self.credentials.host,
            path=path,
            headers={
                **signing_headers,
                "x-access-token": self.credentials.access_token,
                "x-signature": signature,
                "x-version": "v2",
            },
        )

    @staticmethod
    def _send(request: HttpRequest) -> HttpResponse:
        url = f"https://{request.host}{request.path}"
        outbound = urllib.request.Request(url, headers=dict(request.headers), method=request.method)
        try:
            with urllib.request.urlopen(outbound, timeout=15) as response:
                raw = response.read().decode("utf-8")
                return HttpResponse(response.status, json.loads(raw) if raw else {})
        except urllib.error.HTTPError as error:
            raw = error.read().decode("utf-8", errors="replace")
            try:
                body: Any = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                body = {}
            return HttpResponse(error.code, body)


@dataclass(frozen=True)
class Capability:
    state: str  # verified, unavailable, or unknown
    http_status: int | None
    code: str | None
    evidence_hash: str | None

    def as_dict(self) -> dict[str, str | int | None]:
        return {"state": self.state, "http_status": self.http_status, "code": self.code, "evidence_hash": self.evidence_hash}


@dataclass(frozen=True)
class ProbeReport:
    environment: str
    generated_at: str
    capabilities: Mapping[str, Capability]

    def redacted_dict(self) -> dict[str, Any]:
        return {
            "environment": self.environment,
            "generated_at": self.generated_at,
            "capabilities": {name: capability.as_dict() for name, capability in self.capabilities.items()},
        }


class CapabilityProbe:
    def __init__(self, client: WebullClient, now: Callable[[], datetime] | None = None) -> None:
        self.client = client
        self._now = now or (lambda: datetime.now(UTC))

    def run(self) -> ProbeReport:
        account = self._request("/trading/accounts/list")
        capabilities: dict[str, Capability] = {
            "account_read": account,
            "authentication": self._authentication_state(account),
            "access_token": self._token_state(account),
        }
        if account.state == "unavailable" and account.code in _TOKEN_CODES:
            capabilities["stock_snapshot"] = Capability("unknown", None, "TOKEN_REQUIRED", None)
            capabilities["option_snapshot"] = Capability("unknown", None, "TOKEN_REQUIRED", None)
        elif account.state == "unavailable" and account.code in _AUTH_CODES:
            capabilities["stock_snapshot"] = Capability("unknown", None, "AUTHENTICATION_REQUIRED", None)
            capabilities["option_snapshot"] = Capability("unknown", None, "AUTHENTICATION_REQUIRED", None)
        else:
            capabilities["stock_snapshot"] = self._request(
                "/market-data/stocks/snapshots/list?symbols=AAPL&category=US_STOCK&extend_hour_required=false&overnight_required=false"
            )
            capabilities["option_snapshot"] = self._request(
                "/market-data/options/snapshots/list?symbols=AAPL&category=US_OPTION"
            )
        return ProbeReport(
            environment=self.client.credentials.environment,
            generated_at=self._now().astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            capabilities=capabilities,
        )

    def _request(self, path: str) -> Capability:
        try:
            response = self.client.get(path)
        except (OSError, urllib.error.URLError):
            return Capability("unknown", None, "NETWORK_ERROR", None)
        code = _body_code(response.body) or None
        evidence_hash = _evidence_hash(response.body)
        if 200 <= response.status < 300:
            return Capability("verified", response.status, code, evidence_hash)
        if response.status == 401 and code in _TOKEN_CODES:
            return Capability("unavailable", response.status, code, evidence_hash)
        if response.status == 403 and code in _SUBSCRIPTION_CODES:
            return Capability("unavailable", response.status, code, evidence_hash)
        return Capability("unknown", response.status, code, evidence_hash)

    @staticmethod
    def _authentication_state(account: Capability) -> Capability:
        if account.state == "verified":
            return Capability("verified", account.http_status, None, account.evidence_hash)
        if account.code in _AUTH_CODES:
            return Capability("unavailable", account.http_status, account.code, account.evidence_hash)
        return Capability("unknown", account.http_status, account.code, account.evidence_hash)

    @staticmethod
    def _token_state(account: Capability) -> Capability:
        if account.state == "verified":
            return Capability("verified", account.http_status, None, account.evidence_hash)
        if account.code in _TOKEN_CODES:
            return Capability("unavailable", account.http_status, account.code, account.evidence_hash)
        return Capability("unknown", account.http_status, account.code, account.evidence_hash)
