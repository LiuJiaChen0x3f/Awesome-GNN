"""Small bounded HTTP client; never log request URLs or response secrets."""
import json
import os
import time
import urllib.error
import urllib.request


class RequestError(RuntimeError):
    pass


def _http_error_detail(exc):
    """Return a short provider message without echoing credentials or bodies."""
    try:
        raw = exc.read(2000).decode("utf-8", errors="replace")
        value = json.loads(raw)
        value = value.get("error", value) if isinstance(value, dict) else value
        if isinstance(value, dict):
            value = value.get("message") or value.get("code") or "request rejected"
        detail = str(value)
    except Exception:
        detail = "request rejected"
    for secret_name in ("LLM_API_KEY", "OPENALEX_API_KEY"):
        secret = os.getenv(secret_name, "")
        if secret:
            detail = detail.replace(secret, "<redacted>")
    return " ".join(detail.split())[:240]


def request(url, *, payload=None, headers=None, timeout=40, attempts=3):
    contact = os.getenv("CONTACT_EMAIL", "")
    default = {"User-Agent": f"Awesome-GNN/0.1 (research digest; {contact})"}
    if payload is not None:
        default["Content-Type"] = "application/json"
    default.update(headers or {})
    body = json.dumps(payload).encode() if payload is not None else None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, data=body, headers=default)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            retryable = exc.code in (408, 429, 500, 502, 503, 504)
            if not retryable or attempt == attempts - 1:
                detail = _http_error_detail(exc)
                raise RequestError(f"HTTP {exc.code}: {detail}") from None
            delay = exc.headers.get("Retry-After", "")
            time.sleep(min(float(delay), 60) if delay.isdigit() else 2 ** (attempt + 1))
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == attempts - 1:
                raise RequestError("network/timeout failure") from None
            time.sleep(2 ** (attempt + 1))
    raise RequestError("no HTTP attempts configured")


def get_json(url, **kwargs):
    return json.loads(request(url, **kwargs))
