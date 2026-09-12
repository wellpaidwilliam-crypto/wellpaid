"""WellPaiD Trader - Web research tool (V0.5, Option A).

READ-ONLY web fetch with hard guards:

- http/https only (no file://, no other schemes)
- link-local/metadata addresses refused (169.254.0.0/16 — cloud
  credential endpoints); loopback explicitly allowed so the agent can
  read local services, everything else must resolve publicly
- 15s timeout, 2 MiB body cap, redirects followed by urllib
- HTML converted to text with the stdlib parser (scripts/styles
  dropped); links extracted (capped)
- No JavaScript execution: JS-rendered pages come back without their
  dynamic content, and results say so

This is a research aid, not a browser: no forms, no cookies, no auth.
"""

import ipaddress
import socket
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Optional

try:
    from agent.tools.base import SafetyClass, Tool, ToolResult
except ImportError:
    from .base import SafetyClass, Tool, ToolResult

_HTTP_TIMEOUT = 15
MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_LINKS = 100
MAX_TEXT_CHARS = 20_000
CACHE_TTL_SECONDS = 600
CACHE_MAX_ENTRIES = 50


def _host_allowed(host: str) -> tuple[bool, str]:
    """Decide whether a URL host may be fetched.

    Returns (allowed, reason). Loopback is allowed (local services);
    link-local (cloud metadata) is refused; unresolvable hosts fail
    closed at fetch time anyway.
    """
    if not host:
        return False, "empty host"
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        try:
            resolved = socket.getaddrinfo(host, None, family=socket.AF_UNSPEC)
        except socket.gaierror:
            return False, "host does not resolve"
        for family, _, _, _, sockaddr in resolved:
            addr = ipaddress.ip_address(sockaddr[0])
            if addr.is_link_local and not addr.is_loopback:
                return False, "link-local addresses are refused"
        return True, "ok"
    if addr.is_loopback:
        return True, "ok"
    if addr.is_link_local:
        return False, "link-local addresses are refused"
    return True, "ok"


class _TextExtractor(HTMLParser):
    """HTML to text: drops scripts/styles, keeps links separately."""

    def __init__(self) -> None:
        """Initialize empty text and link collectors."""
        super().__init__()
        self.chunks: list[str] = []
        self.links: list[dict] = []
        self._skip = False
        self._title_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        """Track skip/title/link state on open tags."""
        tag = tag.lower()
        if tag in ("script", "style", "noscript"):
            self._skip = True
        elif tag == "title":
            self._in_title = True
        elif tag == "a":
            href = dict(attrs).get("href", "")
            if href:
                self.links.append({"href": href, "text": ""})

    def handle_endtag(self, tag: str) -> None:
        """Release skip/title state on close tags."""
        tag = tag.lower()
        if tag in ("script", "style", "noscript"):
            self._skip = False
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        """Collect visible text, title text and link labels."""
        if self._skip:
            return
        if self._in_title:
            self._title_parts.append(data.strip())
            return
        stripped = data.strip()
        if stripped:
            self.chunks.append(stripped)
            if self.links:
                self.links[-1]["text"] = (
                    self.links[-1]["text"] + " " + stripped
                ).strip()


class WebFetchTool(Tool):
    """Fetch a page and return text + links. GET only, capped, guarded."""

    name = "webfetch"
    description = (
        "Fetch an http(s) URL and return its text and links "
        "(no JS execution, 2 MiB cap, metadata addresses refused)."
    )
    safety = SafetyClass.READ_ONLY
    schema = {
        "url": {
            "type": "string",
            "required": True,
            "description": "http(s) URL to fetch.",
        },
        "max_links": {
            "type": "integer",
            "required": False,
            "description": "Max links to return (default 20, max 100).",
        },
        "fresh": {
            "type": "boolean",
            "required": False,
            "description": "Skip the cache and refetch (default false).",
        },
    }

    def __init__(self) -> None:
        """Initialize an empty TTL cache (URL -> (stored_at, payload))."""
        import time as _time

        self._now = _time.monotonic
        self._cache: dict[str, tuple[float, dict]] = {}

    def _cached(self, url: str) -> Optional[dict]:
        entry = self._cache.get(url)
        if entry is None:
            return None
        stored_at, payload = entry
        if self._now() - stored_at > CACHE_TTL_SECONDS:
            del self._cache[url]
            return None
        return payload

    def _store(self, url: str, payload: dict) -> None:
        while len(self._cache) >= CACHE_MAX_ENTRIES:
            oldest = min(self._cache.items(), key=lambda kv: kv[1][0])[0]
            del self._cache[oldest]
        self._cache[url] = (self._now(), payload)

    def execute(self, args: dict) -> ToolResult:
        url = args["url"].strip()
        try:
            parsed = urllib.parse.urlparse(url)
        except ValueError:
            return ToolResult(False, "invalid URL")
        if parsed.scheme not in ("http", "https"):
            return ToolResult(False, "only http(s) URLs may be fetched")
        if not parsed.hostname:
            return ToolResult(False, "URL has no host")
        allowed, reason = _host_allowed(parsed.hostname)
        if not allowed:
            return ToolResult(False, f"refused host: {reason}")
        max_links = args.get("max_links", 20)
        if isinstance(max_links, bool) or not isinstance(max_links, int):
            return ToolResult(False, "max_links must be an integer")
        max_links = max(0, min(MAX_LINKS, max_links))
        if not args.get("fresh", False):
            cached = self._cached(url)
            if cached is not None:
                links = cached.get("links", [])[:max_links]
                return ToolResult(
                    True,
                    f"{cached.get('title') or cached.get('url')}: "
                    f"{len(cached.get('text', ''))} chars, {len(links)} link(s)",
                    data={**cached, "links": links},
                    warnings=cached.get("warnings", [])
                    + ["served from cache (10 min TTL); pass fresh=true to refetch"],
                )
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "WellPaiD-Trader/0.5 (research)"}
            )
            with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as response:
                content_type = response.headers.get_content_type()
                raw = response.read(MAX_BODY_BYTES + 1)
        except Exception as exc:  # noqa: BLE001 - network safety net
            return ToolResult(
                False, f"fetch failed: {type(exc).__name__}",
                warnings=["network failures are reported, never raised"],
            )
        truncated = len(raw) > MAX_BODY_BYTES
        raw = raw[:MAX_BODY_BYTES]
        final_url = response.geturl()
        if "html" in content_type:
            extractor = _TextExtractor()
            try:
                extractor.feed(
                    raw.decode("utf-8", errors="replace")
                )
            except Exception:  # noqa: BLE001 - malformed markup guard
                pass
            text = " ".join(extractor.chunks)[:MAX_TEXT_CHARS]
            title = " ".join(extractor._title_parts).strip()
            links = [
                {
                    "href": urllib.parse.urljoin(final_url, link["href"]),
                    "text": link["text"][:200],
                }
                for link in extractor.links
            ]
            warnings = ["no JavaScript was executed; dynamic content is absent"]
            if truncated:
                warnings.append("body truncated at 2 MiB")
            payload = {
                "url": final_url,
                "title": title,
                "text": text,
                "links": links,
                "warnings": warnings,
            }
            self._store(url, payload)
            shown = links[:max_links]
            return ToolResult(
                True,
                f"{title or final_url}: {len(text)} chars, {len(shown)} link(s)",
                data={**payload, "links": shown},
                warnings=warnings,
            )
        text = raw.decode("utf-8", errors="replace")[:MAX_TEXT_CHARS]
        warnings = ["non-HTML content returned as plain text"]
        if truncated:
            warnings.append("body truncated at 2 MiB")
        payload = {
            "url": final_url,
            "title": "",
            "text": text,
            "links": [],
            "content_type": content_type,
            "warnings": warnings,
        }
        self._store(url, payload)
        return ToolResult(
            True,
            f"{final_url}: {content_type}, {len(raw)} bytes",
            data={**payload, "links": []},
            warnings=warnings,
        )
