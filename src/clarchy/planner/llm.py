"""Model access for the AI planner.

The planner talks to an `LLM`: an object with a `model` name and an async `create(**params)`
that takes Messages API parameters and returns the response as a plain dict. Keeping the
transport this thin means the agent loop is the same whether Claude is reached through the
Anthropic API or Amazon Bedrock, and tests can script responses without a network.

Configuration (environment):
  CLARCHY_LLM    anthropic | bedrock | huggingface | ollama | openai-compatible | rules
                     (default: anthropic when ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN is set,
                     huggingface when HF_TOKEN is set, otherwise rules)
  CLARCHY_LLM_BASE_URL, CLARCHY_LLM_API_KEY   for ollama / openai-compatible endpoints
  CLARCHY_MODEL  model id (default: DEFAULT_MODEL below; on Bedrock, the same id with
                     the "anthropic." prefix)
  AWS_REGION         region for Bedrock
"""

from __future__ import annotations

import os
from typing import Any, Protocol

DEFAULT_MODEL = "claude-opus-5-5"
# Server-side refusal fallback: if a request is declined, the API retries it on the model
# Anthropic recommends for that category. Claude API only; not available on Bedrock.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMError(RuntimeError):
    """The model call failed in a way the user should hear about."""


class LLM(Protocol):
    model: str
    label: str

    async def create(self, **params: Any) -> dict[str, Any]: ...


class AnthropicLLM:
    """Claude through the Anthropic API, with server-side refusal fallbacks enabled."""

    def __init__(self, model: str = DEFAULT_MODEL, client: Any = None, fallbacks: bool = True):
        import anthropic

        self.model = model
        self.label = f"{model} (Anthropic API)"
        self.client = client or anthropic.AsyncAnthropic()
        self.fallbacks = fallbacks

    async def create(self, **params: Any) -> dict[str, Any]:
        import anthropic

        try:
            if self.fallbacks:
                message = await self.client.beta.messages.create(
                    model=self.model, betas=[FALLBACK_BETA], fallbacks="default", **params
                )
            else:
                message = await self.client.messages.create(model=self.model, **params)
        except anthropic.AuthenticationError as exc:
            raise LLMError("The Anthropic API rejected the credentials.") from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("The Anthropic API rate limit was reached; try again shortly.") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"The Anthropic API returned an error ({exc.status_code}).") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("Could not reach the Anthropic API.") from exc
        return message.to_dict()


class BedrockLLM:
    """Claude through Amazon Bedrock (Messages API endpoint)."""

    def __init__(self, model: str | None = None, region: str | None = None, client: Any = None):
        import anthropic

        self.model = model or f"anthropic.{DEFAULT_MODEL}"
        region = region or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        if client is None and not region:
            raise LLMError("Set AWS_REGION to use Claude on Amazon Bedrock.")
        self.label = f"{self.model} (Amazon Bedrock, {region})"
        self.client = client or anthropic.AsyncAnthropicBedrockMantle(aws_region=region)

    async def create(self, **params: Any) -> dict[str, Any]:
        import anthropic

        try:
            message = await self.client.messages.create(model=self.model, **params)
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Amazon Bedrock returned an error ({exc.status_code}).") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("Could not reach Amazon Bedrock.") from exc
        return message.to_dict()


def llm_from_env() -> LLM | None:
    """The configured model, or None for rule-based planning."""
    choice = os.environ.get("CLARCHY_LLM", "").strip().lower()
    if not choice:
        if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
            choice = "anthropic"
        elif os.environ.get("HF_TOKEN"):
            choice = "huggingface"
        else:
            choice = "rules"
    model = os.environ.get("CLARCHY_MODEL") or None
    if choice == "anthropic":
        return AnthropicLLM(model=model or DEFAULT_MODEL)
    if choice == "bedrock":
        return BedrockLLM(model=model)
    if choice in ("huggingface", "ollama", "openai-compatible"):
        from clarchy.planner import openai_compat as oc

        if choice == "huggingface":
            token = os.environ.get("HF_TOKEN") or os.environ.get("CLARCHY_LLM_API_KEY")
            if not token:
                raise LLMError("Set HF_TOKEN to use open-source models on Hugging Face.")
            name = model or oc.HUGGING_FACE_MODEL
            return oc.OpenAICompatLLM(name, oc.HUGGING_FACE_URL, token, f"{name} (Hugging Face)")
        if choice == "ollama":
            name = model or oc.OLLAMA_MODEL
            url = os.environ.get("CLARCHY_LLM_BASE_URL") or oc.OLLAMA_URL
            return oc.OpenAICompatLLM(name, url, None, f"{name} (Ollama)")
        url = os.environ.get("CLARCHY_LLM_BASE_URL")
        if not url or not model:
            raise LLMError("Set CLARCHY_LLM_BASE_URL and CLARCHY_MODEL for this endpoint.")
        return oc.OpenAICompatLLM(model, url, os.environ.get("CLARCHY_LLM_API_KEY"))
    if choice in ("rules", "none", "off"):
        return None
    raise LLMError(
        f"Unknown CLARCHY_LLM value {choice!r}; use anthropic, bedrock, huggingface, "
        "ollama, openai-compatible or rules."
    )
