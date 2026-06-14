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
        """POST to a Catalyst QuickML LLM Serving endpoint (RAG-grounded).

        Deploy note: keep prompts small (budget). The request/response shape below is
        the documented QuickML serving contract; validate against your endpoint. Not
        runnable locally — use LLM_PROVIDER=mock for dev.
        """
        import httpx

        ctx = context or []
        grounding = "\n".join(f"- {c}" for c in ctx[:5])
        system = (
            "You are a crime-intelligence analyst for the Karnataka State Police. "
            "Answer concisely and only from the provided context."
        )
        user = prompt if not grounding else f"{prompt}\n\nContext:\n{grounding}"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": 400,
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        with httpx.Client(timeout=25) as client:
            resp = client.post(self.endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        # tolerate OpenAI-style or {output/text} shapes
        text = (
            (data.get("choices", [{}])[0].get("message", {}) or {}).get("content")
            or data.get("output")
            or data.get("text")
            or ""
        ).strip()
        return LLMResult(text=text, provider="quickml", model=self.model, grounded_on=ctx[:5])


@lru_cache
def get_llm() -> LLMProvider:
    s = get_settings()
    if s.llm_provider == "quickml":
        return QuickMLProvider(s.quickml_endpoint, s.quickml_api_key, s.quickml_model)
    return MockProvider()
