"""WebFetch tool — fetch URL and extract text content."""

import html as html_module
import ipaddress
import re
import socket
from urllib.parse import urlparse

from myaicoder.tools.base import Tool, ToolResult

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_private_url(url: str) -> str | None:
    """Check if URL resolves to a private/loopback IP.

    Returns error message if blocked, None if safe.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return "Invalid URL: no hostname"

    try:
        infos = socket.getaddrinfo(hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
        for _family, _, _, _, sockaddr in infos:
            ip = ipaddress.ip_address(sockaddr[0])
            for network in _BLOCKED_NETWORKS:
                if ip in network:
                    return f"Blocked: URL resolves to private IP {ip}"
    except socket.gaierror:
        return f"DNS resolution failed for: {hostname}"

    return None

MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5MB
REQUEST_TIMEOUT = 10
USER_AGENT = "myaicoder/1.0 (Documentation Fetcher)"
ALLOWED_CONTENT_TYPES = {"text/html", "text/plain", "application/json"}


class WebFetchTool(Tool):
    @property
    def name(self) -> str:
        return "WebFetch"

    @property
    def description(self) -> str:
        return (
            "Fetch a URL and extract its text content. "
            "HTML pages are converted to plain text (scripts/styles removed). "
            "Use for reading documentation, API references, etc."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to fetch (http/https only).",
                },
                "max_length": {
                    "type": "integer",
                    "description": "Max output characters (default: 20000).",
                },
            },
            "required": ["url"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        url = kwargs.get("url", "")
        max_length = kwargs.get("max_length", 20000)

        if not url:
            return ToolResult(success=False, output="", error="url is required")

        # Validate URL scheme
        if not url.startswith(("http://", "https://")):
            return ToolResult(
                success=False, output="",
                error="Only http:// and https:// URLs are allowed",
            )

        # SSRF protection: block private/loopback IPs
        ssrf_error = _is_private_url(url)
        if ssrf_error:
            return ToolResult(success=False, output="", error=ssrf_error)

        try:
            import httpx

            async with httpx.AsyncClient(
                timeout=REQUEST_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
        except ImportError:
            return ToolResult(
                success=False, output="",
                error="httpx is required. Install with: pip install httpx",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Fetch failed: {e}")

        # Check content length
        if len(response.content) > MAX_RESPONSE_BYTES:
            return ToolResult(
                success=False, output="",
                error=f"Response too large: {len(response.content)} bytes (max {MAX_RESPONSE_BYTES})",
            )

        # Check content type
        content_type = response.headers.get("content-type", "").split(";")[0].strip()
        if content_type not in ALLOWED_CONTENT_TYPES:
            return ToolResult(
                success=False, output="",
                error=f"Unsupported content type: {content_type}",
            )

        text = response.text

        # Convert HTML to plain text
        if "html" in content_type:
            text = _html_to_text(text)

        # Truncate
        if len(text) > max_length:
            text = text[:max_length] + "\n... (truncated)"

        return ToolResult(success=True, output=text)


def _html_to_text(html: str) -> str:
    """Convert HTML to plain text.

    Order matters (FB-B):
    1. Remove <script>...</script> blocks
    2. Remove <style>...</style> blocks
    3. Remove non-content tags (nav, footer, header)
    4. Replace block tags with newlines
    5. Remove remaining HTML tags
    6. Decode HTML entities
    7. Collapse whitespace
    """
    # Step 1-2: FB-B — remove script/style FIRST to prevent JS/CSS token waste
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Step 3: Remove non-content structural tags
    for tag in ("nav", "footer", "header", "aside"):
        text = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Step 4: Block tags → newlines
    text = re.sub(r"<(?:br|p|div|li|h[1-6]|tr|dt|dd)[^>]*>", "\n", text, flags=re.IGNORECASE)

    # Step 5: Remove all remaining tags
    text = re.sub(r"<[^>]+>", "", text)

    # Step 6: Decode HTML entities
    text = html_module.unescape(text)

    # Step 7: Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)

    return text.strip()
