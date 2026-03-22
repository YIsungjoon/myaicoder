"""WebFetch tool — fetch URL and extract text content."""

import html as html_module
import re

from myaicoder.tools.base import Tool, ToolResult

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
