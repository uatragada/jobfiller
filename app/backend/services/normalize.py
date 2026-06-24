from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse, urlunparse


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:80] or "job"


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    path = parsed.path.rstrip("/")
    query = ""
    if "linkedin.com" in parsed.netloc and "/jobs/view/" in path:
        match = re.search(r"(\d+)", path)
        if match:
            path = f"/jobs/view/{match.group(1)}"
    elif parsed.query:
        query = parsed.query
    return urlunparse((parsed.scheme or "https", parsed.netloc.lower(), path, "", query, ""))


def unsafe_import_url_reason(url: str) -> str | None:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "URL must use http or https and include a host."
    if parsed.username or parsed.password:
        return "URL must not contain embedded credentials."

    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if not hostname:
        return "URL must include a host."
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".localhost"):
        return "localhost URLs are unsafe for job import."

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return None

    if (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        return "local, private, metadata, or reserved IP addresses are unsafe for job import."
    return None


def unsafe_loopback_http_url_reason(url: str) -> str | None:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "URL must use http or https and include a host."
    if parsed.username or parsed.password:
        return "URL must not contain embedded credentials."

    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if not hostname:
        return "URL must include a host."
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".localhost"):
        return None

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return "URL must use a loopback host such as localhost or 127.0.0.1."

    if address.is_loopback:
        return None
    return "URL must use a loopback host such as localhost or 127.0.0.1."


def infer_from_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    path = parsed.path.replace("-", " ")
    title = "Imported Job"
    company = "Unknown Company"
    if "/jobs/view/" in parsed.path:
        pieces = [p for p in re.split(r"[/_-]+", parsed.path) if p and not p.isdigit()]
        useful = [p for p in pieces if p.lower() not in {"jobs", "view", "at"}]
        if useful:
            title = " ".join(useful[:5]).title()
    return company, title
