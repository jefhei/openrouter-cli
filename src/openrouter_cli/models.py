"""Data models for OpenRouter API responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ModelPricing(BaseModel):
    """Pricing information for a model."""

    prompt: float = Field(description="Cost per prompt token")
    completion: float = Field(description="Cost per completion token")
    image: float | None = Field(default=None, description="Cost per image")
    request: float | None = Field(default=None, description="Cost per request")


class ModelInfo(BaseModel):
    """Information about an OpenRouter model."""

    id: str = Field(description="Model identifier (author/slug)")
    name: str = Field(description="Human-readable model name")
    description: str | None = Field(default=None, description="Model description")
    context_length: int = Field(description="Maximum context length in tokens")
    pricing: ModelPricing = Field(description="Pricing information")
    top_provider: dict[str, Any] | None = Field(default=None, description="Top provider info")
    architecture: dict[str, Any] | None = Field(default=None, description="Model architecture")
    per_request_limits: dict[str, Any] | None = Field(default=None, description="Rate limits")

    @property
    def author(self) -> str:
        """Get the model author/provider."""
        return self.id.split("/")[0] if "/" in self.id else ""

    @property
    def slug(self) -> str:
        """Get the model slug."""
        return self.id.split("/")[1] if "/" in self.id else self.id


class Message(BaseModel):
    """A chat message."""

    role: str = Field(description="Message role: system, user, assistant, or tool")
    content: str | list[dict[str, Any]] = Field(description="Message content")
    name: str | None = Field(default=None, description="Optional name for the message author")
    tool_calls: list[dict[str, Any]] | None = Field(default=None, description="Tool calls")
    tool_call_id: str | None = Field(default=None, description="Tool call ID for tool responses")


class Choice(BaseModel):
    """A completion choice."""

    index: int = Field(description="Choice index")
    message: Message = Field(description="The generated message")
    finish_reason: str | None = Field(default=None, description="Why generation stopped")


class Usage(BaseModel):
    """Token usage information."""

    prompt_tokens: int = Field(description="Number of prompt tokens")
    completion_tokens: int = Field(description="Number of completion tokens")
    total_tokens: int = Field(description="Total tokens used")


class ChatCompletion(BaseModel):
    """A chat completion response."""

    id: str = Field(description="Completion ID")
    object: str = Field(default="chat.completion", description="Object type")
    created: int = Field(description="Unix timestamp of creation")
    model: str = Field(description="Model used for completion")
    choices: list[Choice] = Field(description="Completion choices")
    usage: Usage | None = Field(default=None, description="Token usage")


class StreamDelta(BaseModel):
    """A streaming response delta."""

    role: str | None = Field(default=None, description="Message role")
    content: str | None = Field(default=None, description="Content delta")
    tool_calls: list[dict[str, Any]] | None = Field(default=None, description="Tool call deltas")


class StreamChoice(BaseModel):
    """A streaming choice."""

    index: int = Field(description="Choice index")
    delta: StreamDelta = Field(description="The delta content")
    finish_reason: str | None = Field(default=None, description="Why generation stopped")


class ChatCompletionChunk(BaseModel):
    """A streaming chat completion chunk."""

    id: str = Field(description="Completion ID")
    object: str = Field(default="chat.completion.chunk", description="Object type")
    created: int = Field(description="Unix timestamp of creation")
    model: str = Field(description="Model used for completion")
    choices: list[StreamChoice] = Field(description="Completion choices")


class GenerationStats(BaseModel):
    """Generation statistics from OpenRouter."""

    id: str = Field(description="Generation ID")
    model: str = Field(description="Model used")
    streamed: bool = Field(description="Whether response was streamed")
    generation_time: float | None = Field(default=None, description="Time to generate in ms")
    created_at: str = Field(description="Creation timestamp")
    tokens_prompt: int = Field(description="Prompt tokens")
    tokens_completion: int = Field(description="Completion tokens")
    native_tokens_prompt: int | None = Field(default=None, description="Native prompt tokens")
    native_tokens_completion: int | None = Field(default=None, description="Native completion tokens")
    num_media_prompt: int | None = Field(default=None, description="Number of media in prompt")
    num_media_completion: int | None = Field(default=None, description="Number of media in completion")
    origin: str | None = Field(default=None, description="Request origin")
    total_cost: float = Field(description="Total cost in USD")


class AccountBalance(BaseModel):
    """Account balance information."""
    credits: float | None = None
    usage: float | None = None
    limit: float | None = None  # Add this field


class Conversation(BaseModel):
    """A saved conversation."""

    id: str = Field(description="Conversation identifier")
    name: str = Field(description="Conversation name")
    model: str = Field(description="Model used in conversation")
    messages: list[Message] = Field(default_factory=list, description="Conversation messages")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation time")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update time")
    total_tokens: int = Field(default=0, description="Total tokens used")
    total_cost: float = Field(default=0.0, description="Total cost in USD")

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation."""
        self.messages.append(Message(role=role, content=content))
        self.updated_at = datetime.now()


class ToolDefinition(BaseModel):
    """A tool/function definition for function calling."""

    type: str = Field(default="function", description="Tool type")
    function: dict[str, Any] = Field(description="Function definition")


class MCPTool(BaseModel):
    """An MCP tool definition."""

    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    input_schema: dict[str, Any] = Field(description="JSON schema for tool input")
