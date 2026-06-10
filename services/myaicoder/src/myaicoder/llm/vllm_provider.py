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
        flat_messages = self._flatten_messages(messages)
        openai_messages = [m.to_openai_dict() for m in flat_messages]

        kwargs: dict = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
            "stop": ["<|im_end|>", "<|endoftext|>", "Observation:", "OBSERVATION:", "[SYSTEM:"],
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

        # ── Fallback Parsing for Hybrid-style tool calls (XML, Markdown JSON, ReAct) ──
        if not parsed_tool_calls:
            import re
            import uuid
            parsed_tool_calls = []

            # 1. XML-style tool calls (<tool_call>...</tool_call>)
            if "<tool_call>" in content:
                tool_blocks = re.findall(r'<tool_call>(.*?)</tool_call>', content, re.DOTALL)
                for block in tool_blocks:
                    func_match = re.search(r'<function=(\w+)>', block)
                    if func_match:
                        func_name = func_match.group(1).strip()
                        params = {}
                        param_matches = re.finditer(r'<parameter=(\w+)>(.*?)</parameter>', block, re.DOTALL)
                        for pm in param_matches:
                            param_name = pm.group(1).strip()
                            param_val = pm.group(2).strip()
                            params[param_name] = param_val
                        
                        parsed_tool_calls.append(
                            ToolCall(
                                id=f"call_{uuid.uuid4().hex[:8]}",
                                name=func_name,
                                arguments=params,
                            )
                        )
                # Clean XML tool calls from content to prevent leak to UI
                content = re.sub(r'<tool_call>.*?</tool_call>', '', content, flags=re.DOTALL).strip()

            # 2. Markdown JSON code blocks (```json ... ```)
            if not parsed_tool_calls and "```json" in content:
                json_blocks = re.findall(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                for block in json_blocks:
                    try:
                        data = json.loads(block.strip())
                        items = data if isinstance(data, list) else [data]
                        for item in items:
                            name = item.get("name") or item.get("function")
                            args = item.get("arguments") or item.get("parameters") or {}
                            if name:
                                if isinstance(args, str):
                                    try:
                                        args = json.loads(args)
                                    except json.JSONDecodeError:
                                        args = {"raw": args}
                                parsed_tool_calls.append(
                                    ToolCall(
                                        id=f"call_{uuid.uuid4().hex[:8]}",
                                        name=name,
                                        arguments=args,
                                    )
                                )
                    except json.JSONDecodeError:
                        pass
                if parsed_tool_calls:
                    content = re.sub(r'```json\s*(.*?)\s*```', '', content, flags=re.DOTALL).strip()

            # 3. ReAct style (Action: name \n Action Input: {args})
            if not parsed_tool_calls and "action:" in content.lower():
                action_matches = re.finditer(r'(?i)action:\s*(\w+)\s*\n\s*action\s*input:\s*(.*?)(?=\n\s*(?:thought|action|observation):|$)', content, re.DOTALL)
                for match in action_matches:
                    func_name = match.group(1).strip()
                    arg_str = match.group(2).strip()
                    params = {}
                    try:
                        params = json.loads(arg_str)
                    except json.JSONDecodeError:
                        pass
                    parsed_tool_calls.append(
                        ToolCall(
                            id=f"call_{uuid.uuid4().hex[:8]}",
                            name=func_name,
                            arguments=params,
                        )
                    )
                if parsed_tool_calls:
                    content = re.sub(r'(?i)action:\s*\w+\s*\n\s*action\s*input:\s*.*?(?=\n\s*(?:thought|action|observation):|$)', '', content, flags=re.DOTALL).strip()

            # 4. Plain text Action style (ACTION: name(arguments))
            if not parsed_tool_calls and "action:" in content.lower():
                action_args_matches = re.finditer(r'(?i)action:\s*(\w+)\s*\(([\s\S]*?)\)(?=\n|$|\s*(?:thought|action|observation):)', content)
                for match in action_args_matches:
                    func_name = match.group(1).strip()
                    arg_str = match.group(2).strip()
                    params = {}
                    if arg_str:
                        try:
                            params = json.loads(arg_str)
                        except json.JSONDecodeError:
                            params = {"raw": arg_str}
                    parsed_tool_calls.append(
                        ToolCall(
                            id=f"call_{uuid.uuid4().hex[:8]}",
                            name=func_name,
                            arguments=params,
                        )
                    )
                if parsed_tool_calls:
                    content = re.sub(r'(?i)action:\s*\w+\s*\(([\s\S]*?)\)(?=\n|$|\s*(?:thought|action|observation):)', '', content, flags=re.DOTALL).strip()

            if parsed_tool_calls:
                # Post-parsing cleanup: remove any leftover XML/parameter tags or action headers
                # to prevent leaking raw model outputs to the UI
                content = re.sub(r'</?(?:tool_call|parameter|function|argument|func)[^>]*>', '', content)
                content = re.sub(r'(?i)action:\s*\w+\s*\(.*?\)', '', content, flags=re.DOTALL)
                content = re.sub(r'(?i)action:\s*\w+\s*\n\s*action\s*input:\s*.*?(?=\n|$)', '', content, flags=re.DOTALL)
                content = re.sub(r'(?i)action:\s*\w+\s*\(.*', '', content)
                content = content.strip()

            if not parsed_tool_calls:
                parsed_tool_calls = None

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
                raise RuntimeError(f"LLM API Error (HTTP {resp.status_code}): {resp.text[:500]}")
            resp.raise_for_status()
            data = resp.json()

        if "error" in data:
            raise RuntimeError(f"LLM API returned error: {data['error']}")
        if "choices" not in data:
            raise RuntimeError(f"LLM API response missing 'choices' key. Keys received: {list(data.keys())}. Response text: {resp.text[:500]}")

        choice = data["choices"][0]["message"]
        choice["_usage"] = data.get("usage", {})
        return choice

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.0,
    ) -> AsyncIterator[str]:
        flat_messages = self._flatten_messages(messages)
        openai_messages = [m.to_openai_dict() for m in flat_messages]

        kwargs: dict = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
            "stop": ["<|im_end|>", "<|endoftext|>", "Observation:", "OBSERVATION:", "[SYSTEM:"],
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

    def _flatten_messages(self, messages: list[Message]) -> list[Message]:
        """Convert tool calls and tool responses to plain assistant/user texts.
        This prevents local LLMs (Qwen/Llama) from losing track of instructions
        and losing tool call context due to incomplete OpenAI compatibility in chat templates.
        """
        # Find the original user request to remind the agent in observations
        original_request = ""
        for m in reversed(messages):
            if m.role == "user" and m.content and not m.content.startswith("[SYSTEM:"):
                clean_content = m.content
                if "User request:" in clean_content:
                    clean_content = clean_content.split("User request:")[-1].strip()
                original_request = clean_content
                break

        flattened = []
        for m in messages:
            if m.role == "assistant":
                content_parts = []
                if m.content:
                    content_parts.append(m.content)
                if m.tool_calls:
                    for tc in m.tool_calls:
                        args_str = json.dumps(tc.arguments, ensure_ascii=False) if isinstance(tc.arguments, dict) else str(tc.arguments)
                        content_parts.append(f"ACTION: {tc.name}({args_str})")
                
                flattened.append(
                    Message(
                        role="assistant",
                        content="\n\n".join(content_parts) if content_parts else "Thinking..."
                    )
                )
            elif m.role == "tool":
                # Prefix observation with a clear system instruction to prevent LLM from mistaking raw content as user messages
                instr = (
                    f"[SYSTEM: This is the raw output/observation of the previous tool call. "
                    f"It is NOT a message from the user. Read and analyze the following content "
                    f"to complete the user's request: '{original_request}']\n\n"
                    f"OBSERVATION:\n{m.content or ''}"
                )
                flattened.append(
                    Message(
                        role="user",
                        content=instr
                    )
                )
            else:
                flattened.append(m)
        return flattened
