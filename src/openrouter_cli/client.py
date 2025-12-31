"""OpenRouter API client."""

import json
from collections.abc import AsyncGenerator, Generator
from typing import Any

import httpx

from .config import ConfigManager, get_config_manager
from .models import (
    AccountBalance,
    ChatCompletion,
    ChatCompletionChunk,
    GenerationStats,
    Message,
    ModelInfo,
    ToolDefinition,
)


class OpenRouterError(Exception):
    """Base exception for OpenRouter errors."""

    def __init__(self, message: str, status_code: int | None = None, error_code: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class AuthenticationError(OpenRouterError):
    """Authentication failed."""

    pass


class RateLimitError(OpenRouterError):
    """Rate limit exceeded."""

    pass


class ModelNotFoundError(OpenRouterError):
    """Model not found."""

    pass


class InsufficientCreditsError(OpenRouterError):
    """Insufficient credits."""

    pass


class OpenRouterClient:
    """Client for interacting with the OpenRouter API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
        config_manager: ConfigManager | None = None,
    ):
        """Initialize the client."""
        self._config = config_manager or get_config_manager()
        self.api_key = api_key or self._config.get_api_key()
        self.base_url = base_url or self._config.get_base_url()
        self.timeout = timeout or self._config.get_timeout()
        self.max_retries = max_retries or self._config.get_max_retries()

        if not self.api_key:
            raise AuthenticationError(
                "API key not found. Set OPENROUTER_API_KEY or run 'openrouter config set api_key <key>'"
            )

        self._client: httpx.Client | None = None
        self._async_client: httpx.AsyncClient | None = None

    def _get_headers(self) -> dict[str, str]:
        """Get request headers."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self._config.config.headers.app_url or "https://github.com/openrouter-cli",
            "X-Title": self._config.config.headers.app_name or "openrouter-cli",
        }
        return headers

    @property
    def client(self) -> httpx.Client:
        """Get or create the sync HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
        return self._client

    @property
    def async_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
        return self._async_client

    def _handle_error(self, response: httpx.Response) -> None:
        """Handle API error responses."""
        if response.status_code == 200:
            return

        try:
            error_data = response.json()
            message = error_data.get("error", {}).get("message", response.text)
            error_code = error_data.get("error", {}).get("code")
        except Exception:
            message = response.text
            error_code = None

        if response.status_code == 401:
            raise AuthenticationError(message, response.status_code, error_code)
        elif response.status_code == 429:
            raise RateLimitError(message, response.status_code, error_code)
        elif response.status_code == 404:
            raise ModelNotFoundError(message, response.status_code, error_code)
        elif response.status_code == 402:
            raise InsufficientCreditsError(message, response.status_code, error_code)
        else:
            raise OpenRouterError(message, response.status_code, error_code)

    def chat_completion(
        self,
        messages: list[Message] | list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        stop: list[str] | None = None,
        stream: bool = False,
        tools: list[ToolDefinition] | list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        response_format: dict[str, Any] | None = None,
        provider: dict[str, Any] | None = None,
    ) -> ChatCompletion:
        """Send a chat completion request."""
        defaults = self._config.config.defaults

        # Convert Message objects to dicts
        msg_list = []
        for msg in messages:
            if isinstance(msg, Message):
                msg_list.append(msg.model_dump(exclude_none=True))
            else:
                msg_list.append(msg)

        payload: dict[str, Any] = {
            "model": model or defaults.model,
            "messages": msg_list,
            "stream": stream,
        }

        # Add optional parameters
        if temperature is not None:
            payload["temperature"] = temperature
        elif defaults.temperature is not None:
            payload["temperature"] = defaults.temperature

        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        elif defaults.max_tokens is not None:
            payload["max_tokens"] = defaults.max_tokens

        if top_p is not None:
            payload["top_p"] = top_p
        elif defaults.top_p is not None:
            payload["top_p"] = defaults.top_p

        if top_k is not None:
            payload["top_k"] = top_k
        elif defaults.top_k is not None:
            payload["top_k"] = defaults.top_k

        if frequency_penalty is not None:
            payload["frequency_penalty"] = frequency_penalty
        elif defaults.frequency_penalty is not None:
            payload["frequency_penalty"] = defaults.frequency_penalty

        if presence_penalty is not None:
            payload["presence_penalty"] = presence_penalty
        elif defaults.presence_penalty is not None:
            payload["presence_penalty"] = defaults.presence_penalty

        if stop:
            payload["stop"] = stop

        if tools:
            tool_list = []
            for tool in tools:
                if isinstance(tool, ToolDefinition):
                    tool_list.append(tool.model_dump())
                else:
                    tool_list.append(tool)
            payload["tools"] = tool_list

        if tool_choice:
            payload["tool_choice"] = tool_choice

        if response_format:
            payload["response_format"] = response_format

        if provider:
            payload["provider"] = provider

        response = self.client.post("/chat/completions", json=payload)
        self._handle_error(response)
        return ChatCompletion.model_validate(response.json())

    def chat_completion_stream(
        self,
        messages: list[Message] | list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        stop: list[str] | None = None,
        tools: list[ToolDefinition] | list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        response_format: dict[str, Any] | None = None,
        provider: dict[str, Any] | None = None,
    ) -> Generator[ChatCompletionChunk, None, None]:
        """Send a streaming chat completion request."""
        defaults = self._config.config.defaults

        # Convert Message objects to dicts
        msg_list = []
        for msg in messages:
            if isinstance(msg, Message):
                msg_list.append(msg.model_dump(exclude_none=True))
            else:
                msg_list.append(msg)

        payload: dict[str, Any] = {
            "model": model or defaults.model,
            "messages": msg_list,
            "stream": True,
        }

        # Add optional parameters (same as non-streaming)
        if temperature is not None:
            payload["temperature"] = temperature
        elif defaults.temperature is not None:
            payload["temperature"] = defaults.temperature

        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        elif defaults.max_tokens is not None:
            payload["max_tokens"] = defaults.max_tokens

        if top_p is not None:
            payload["top_p"] = top_p
        elif defaults.top_p is not None:
            payload["top_p"] = defaults.top_p

        if top_k is not None:
            payload["top_k"] = top_k
        elif defaults.top_k is not None:
            payload["top_k"] = defaults.top_k

        if frequency_penalty is not None:
            payload["frequency_penalty"] = frequency_penalty
        elif defaults.frequency_penalty is not None:
            payload["frequency_penalty"] = defaults.frequency_penalty

        if presence_penalty is not None:
            payload["presence_penalty"] = presence_penalty
        elif defaults.presence_penalty is not None:
            payload["presence_penalty"] = defaults.presence_penalty

        if stop:
            payload["stop"] = stop

        if tools:
            tool_list = []
            for tool in tools:
                if isinstance(tool, ToolDefinition):
                    tool_list.append(tool.model_dump())
                else:
                    tool_list.append(tool)
            payload["tools"] = tool_list

        if tool_choice:
            payload["tool_choice"] = tool_choice

        if response_format:
            payload["response_format"] = response_format

        if provider:
            payload["provider"] = provider

        with self.client.stream("POST", "/chat/completions", json=payload) as response:
            self._handle_error(response)
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = ChatCompletionChunk.model_validate(json.loads(data))
                        yield chunk
                    except Exception:
                        continue

    async def achat_completion(
        self,
        messages: list[Message] | list[dict[str, Any]],
        model: str | None = None,
        **kwargs: Any,
    ) -> ChatCompletion:
        """Send an async chat completion request."""
        defaults = self._config.config.defaults

        # Convert Message objects to dicts
        msg_list = []
        for msg in messages:
            if isinstance(msg, Message):
                msg_list.append(msg.model_dump(exclude_none=True))
            else:
                msg_list.append(msg)

        payload: dict[str, Any] = {
            "model": model or defaults.model,
            "messages": msg_list,
            "stream": False,
        }
        payload.update(kwargs)

        response = await self.async_client.post("/chat/completions", json=payload)
        self._handle_error(response)
        return ChatCompletion.model_validate(response.json())

    async def achat_completion_stream(
        self,
        messages: list[Message] | list[dict[str, Any]],
        model: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """Send an async streaming chat completion request."""
        defaults = self._config.config.defaults

        # Convert Message objects to dicts
        msg_list = []
        for msg in messages:
            if isinstance(msg, Message):
                msg_list.append(msg.model_dump(exclude_none=True))
            else:
                msg_list.append(msg)

        payload: dict[str, Any] = {
            "model": model or defaults.model,
            "messages": msg_list,
            "stream": True,
        }
        payload.update(kwargs)

        async with self.async_client.stream("POST", "/chat/completions", json=payload) as response:
            self._handle_error(response)
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = ChatCompletionChunk.model_validate(json.loads(data))
                        yield chunk
                    except Exception:
                        continue

    def list_models(self) -> list[ModelInfo]:
        """List all available models."""
        response = self.client.get("/models")
        self._handle_error(response)
        data = response.json()
        models = []
        for model_data in data.get("data", []):
            try:
                models.append(ModelInfo.model_validate(model_data))
            except Exception:
                continue
        return models

    def get_model(self, model_id: str) -> ModelInfo:
        """Get information about a specific model."""
        # Try the direct endpoint first
        response = self.client.get(f"/models/{model_id}")
        if response.status_code == 200:
            return ModelInfo.model_validate(response.json())

        # Fall back to listing all models and filtering
        models = self.list_models()
        for model in models:
            if model.id == model_id:
                return model

        raise ModelNotFoundError(f"Model '{model_id}' not found")

    def get_generation_stats(self, generation_id: str) -> GenerationStats:
        """Get statistics for a generation."""
        response = self.client.get(f"/generation?id={generation_id}")
        self._handle_error(response)
        return GenerationStats.model_validate(response.json()["data"])

    def get_account_balance(self) -> AccountBalance:
        """Get account balance information."""
        response = self.client.get("/auth/key")
        self._handle_error(response)
        data = response.json()["data"]
    
        # Handle None values - API returns null for limit on pay-as-you-go accounts
        limit = data.get("limit")
        usage = data.get("usage") or 0.0
    
        # If limit is None, user has pay-as-you-go (no pre-purchased credits)
        if limit is None:
            credits = None  # Indicates unlimited/pay-as-you-go
        else:
            credits = limit - usage
    
        return AccountBalance(
            credits=credits,
            usage=usage,
            limit=limit,  # Add this field to track account type
        )

    async def aclose(self) -> None:
        """Close the HTTP clients asynchronously.
        
        This is the preferred method for cleanup in async contexts.
        Use this method or the async context manager (async with) when
        working with async operations.
        """
        if self._client:
            self._client.close()
            self._client = None
        if self._async_client:
            await self._async_client.aclose()
            self._async_client = None

    def close(self) -> None:
        """Close the HTTP clients.
        
        For proper async client cleanup in async contexts, prefer using
        `aclose()` or the async context manager (`async with`).
        
        When called from a sync context with an existing async client,
        this method will attempt to close it gracefully but may emit
        a ResourceWarning if cleanup fails.
        """
        if self._client:
            self._client.close()
            self._client = None
        if self._async_client:
            import asyncio
            import warnings

            async_client = self._async_client
            self._async_client = None  # Clear reference immediately
            
            try:
                # Check if we're inside a running event loop
                try:
                    loop = asyncio.get_running_loop()
                    # We're in an async context - schedule cleanup as a task
                    # The task will complete after close() returns
                    loop.create_task(async_client.aclose())
                except RuntimeError:
                    # No running loop - safe to run synchronously
                    asyncio.run(async_client.aclose())
            except Exception as e:
                # Emit warning instead of silently failing
                warnings.warn(
                    f"Failed to cleanly close async client: {e}. "
                    "Consider using 'async with' or calling aclose() directly.",
                    ResourceWarning,
                    stacklevel=2,
                )

    def __enter__(self) -> "OpenRouterClient":
        """Sync context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Sync context manager exit."""
        self.close()

    async def __aenter__(self) -> "OpenRouterClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.aclose()
