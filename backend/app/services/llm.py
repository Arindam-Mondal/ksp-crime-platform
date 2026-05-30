"""
THE single gate for all LLM / RAG access (see CLAUDE.md).

Every natural-language feature calls `get_llm().complete(...)`. Nothing else in the
codebase may import an LLM SDK. This keeps the one undisclosed-cost dependency
(Catalyst QuickML LLM Serving + RAG) swappable and easy to throttle or disable.

Providers:
  * mock     -> deterministic canned answers; spends no credits (default for local dev).
  * quickml  -> Catalyst QuickML LLM Serving endpoint (wired in Phase 4).
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.config import get_settings


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    grounded_on: list[str]  # ids/snippets the answer was grounded on (RAG)


class LLMProvider:
    def complete(self, prompt: str, context: list[str] | None = None) -> LLMResult:  # pragma: no cover
        raise NotImplementedError


class MockProvider(LLMProvider):
    """No-cost stand-in so the app is fully runnable without QuickML access."""

    def complete(self, prompt: str, context: list[str] | None = None) -> LLMResult:
        ctx = context or []
        preview = "; ".join(ctx[:3])
        text = (
            "[mock LLM] This is a placeholder answer. With QuickML enabled, the model "
            "would answer the question grounded on the retrieved records. "
            f"Question: {prompt.strip()[:160]} "
            + (f"| Grounded on: {preview}" if preview else "")
        )
        return LLMResult(text=text, provider="mock", model="mock", grounded_on=ctx[:5])


class QuickMLProvider(LLMProvider):
    """Catalyst QuickML LLM Serving + RAG. Wired in Phase 4.

    Keep prompts small and tear the endpoint down when idle (budget guardrail).
    """

    def __init__(self, endpoint: str, api_key: str, model: str):
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model

    def complete(self, prompt: str, context: list[str] | None = None) -> LLMResult:
        raise NotImplementedError(
            "QuickMLProvider not wired yet. Set LLM_PROVIDER=quickml and implement the "
            "HTTP call to QUICKML_ENDPOINT in Phase 4."
        )


@lru_cache
def get_llm() -> LLMProvider:
    s = get_settings()
    if s.llm_provider == "quickml":
        return QuickMLProvider(s.quickml_endpoint, s.quickml_api_key, s.quickml_model)
    return MockProvider()
