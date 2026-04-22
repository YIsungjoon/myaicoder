"""OpenAI-compatible LLM provider (vLLM, llama-cpp-python, etc.)."""

import json
import logging
from typing import AsyncIterator

import httpx
from openai import AsyncOpenAI

from myaicoder.llm.base import LLMProvider, LLMResponse, Message, ToolCall, Usage

logger = logging.getLogger(__name__)

_PROPS_PATH = "/props"
_MODELS_PATH = "/v1/models"
_MAX_TOKENS_RATIO = 0.5  # use at most half the context window for output


class VLLMProvider(LLMProvider):
    """LLM provider that connects to any OpenAI-compatible API server.

    Supports vLLM, llama-cpp-python, llama.cpp server, Ollama, etc.
    Handles reasoning_content field (thinking mode) from compatible models.
    All connection params come from AppConfig — no defaults hardcoded here.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080/v1",
        model: str = "",
        api_key: str = "",
        max_tokens: int = 4096,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = AsyncOpenAI(base_url=self.base_url, api_key=api_key or "not-needed")

    # ── Auto-configuration ──────────────────────────────────────────────────

    def auto_configure(self) -> None:
        """Fetch server info and set model + max_tokens automatically.

        Tries /props first (llama-server), then /v1/models as fallback.
        Silently skips on any network error so startup never blocks.
        """
        server_base = self.base_url.removesuffix("/v1")
        try:
            with httpx.Client(timeout=5.0) as client:
                props = self._fetch_props(client, server_base)
                if props:
                    self._apply_props(props)
                    return
                models = self._fetch_models(client, server_base)
                if models:
                    self._apply_models(models)
        except Exception as exc:
            logger.warning("auto_configure failed, using existing values: %s", exc)

    def _fetch_props(self, client: httpx.Client, server_base: str) -> dict | None:
        try:
            resp = client.get(f"{server_base}{_PROPS_PATH}")
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def _fetch_models(self, client: httpx.Client, server_base: str) -> dict | None:
        try:
            resp = client.get(f"{server_base}{_MODELS_PATH}")
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def _apply_props(self, props: dict) -> None:
        """Apply llama-server /props response."""
        if not self.model:
            alias = props.get("model_alias", "")
            if alias:
                self.model = alias
                logger.info("auto_configure: model = %s", self.model)

        n_ctx = props.get("default_generation_settings", {}).get("n_ctx") or props.get("n_ctx")
        if n_ctx:
            safe_max = max(512, int(n_ctx * _MAX_TOKENS_RATIO))
            self.max_tokens = safe_max
            logger.info("auto_configure: n_ctx=%d → max_tokens=%d", n_ctx, safe_max)

    def _apply_models(self, data: dict) -> None:
        """Apply /v1/models response as fallback."""
        if not self.model:
            items = data.get("data", [])
            if items:
                self.model = items[0].get("id", "")
                logger.info("auto_configure: model = %s (from /v1/models)", self.model)

    # ── Inference ───────────────────────────────────────────────────────────

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        openai_messages = [m.to_openai_dict() for m in messages]

        kwargs: dict = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        raw_response = await self._raw_chat(openai_messages, kwargs)

        content = raw_response.get("content", "") or ""
        reasoning = raw_response.get("reasoning_content", "")
        raw_tool_calls = raw_response.get("tool_calls")

        # Only surface reasoning as content when there are no tool calls.
        # When tool_calls are present the XML in reasoning_content is internal
        # model formatting — showing it would leak raw <tool_call> tags to UI.
        if not content and reasoning and not raw_tool_calls:
            content = reasoning

        self._last_reasoning = reasoning if reasoning else None

        parsed_tool_calls = None
        if raw_tool_calls:
            parsed_tool_calls = []
            for tc in raw_tool_calls:
                arguments = tc["function"]["arguments"]
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {"raw": arguments}
                parsed_tool_calls.append(
                    ToolCall(
                        id=tc["id"],
                        name=tc["function"]["name"],
                        arguments=arguments,
                    )
                )

        raw_usage = raw_response.get("_usage", {})
        usage = Usage(
            prompt_tokens=raw_usage.get("prompt_tokens", 0),
            completion_tokens=raw_usage.get("completion_tokens", 0),
            total_tokens=raw_usage.get("total_tokens", 0),
        )

        return LLMResponse(
            content=content,
            tool_calls=parsed_tool_calls,
            usage=usage,
        )

    async def _raw_chat(self, messages: list[dict], kwargs: dict) -> dict:
        """Make raw HTTP request to capture all fields including reasoning_content."""
        model = kwargs.get("model", self.model)
        payload: dict = {
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.0),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
        }
        if model:
            payload["model"] = model
        if "tools" in kwargs:
            payload["tools"] = kwargs["tools"]
            payload["tool_choice"] = kwargs.get("tool_choice", "auto")

        headers = {}
        if self.api_key and self.api_key.strip() and self.api_key not in ("", "not-needed"):
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=3600.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            if resp.status_code >= 400:
                logger.error("LLM request failed [%s]: %s", resp.status_code, resp.text[:2000])
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]["message"]
        choice["_usage"] = data.get("usage", {})
        return choice

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        openai_messages = [m.to_openai_dict() for m in messages]

        kwargs: dict = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        stream = await self.client.chat.completions.create(**kwargs)

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def health_check(self) -> bool:
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False
