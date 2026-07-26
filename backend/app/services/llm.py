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
    """Catalyst QuickML LLM Serving — GLM-4.7-Flash chat endpoint.

    Confirmed directly from the endpoint's own "Model Details" / "Sample Request and
    Response" tab in the QuickML console (Qwen 2.5-14B Instruct was deprecated and
    migrated off — see console banner, cutover 2026-07-31). Real contract for the
    shared LLM Serving chat endpoint (NOT the older custom-pipeline-endpoint contract):

        POST <project-scoped chat URL, e.g. .../quickml/v1/project/<id>/glm/chat>
        Headers:
            Authorization: Zoho-oauthtoken <access-token>   (scope QuickML.deployment.READ,
                                                               generated at api-console.zoho.com)
            CATALYST-ORG: <org_id>
            Content-Type: application/json
        Body: OpenAI-compatible chat-completions shape — model, messages[], max_tokens,
        temperature, stream, optionally tools[]/tool_choice/chat_template_kwargs.

    Note: no X-QUICKML-ENDPOINT-KEY and no Environment header for this endpoint — those
    belonged to the older custom-pipeline-endpoint auth contract and don't apply to the
    shared generative-AI chat endpoints. The console's own auto-generated code sample
    shows "Authorization: Bearer YOUR_TOKEN" instead of the Zoho-oauthtoken scheme shown
    in its own Headers box just above it — that looks like stale boilerplate; the Headers
    box is what we trust. If Zoho-oauthtoken gets rejected, Bearer is the fallback to try.

    Access tokens (Zoho-oauthtoken) expire after 1 hour — a token pasted into .env goes
    stale mid-demo. Zoho's Self Client flow (api-console.zoho.com) gives you, once, an
    access token + a REFRESH token that never expires:
    https://www.zoho.com/accounts/protocol/oauth/self-client/authorization-code-flow.html
    So this provider holds client_id/client_secret/refresh_token and mints a fresh access
    token on demand — cached in-process, renewed ~60s before its 3600s lifetime is up —
    via POST {accounts_url} grant_type=refresh_token
    (https://www.zoho.com/accounts/protocol/oauth/web-apps/access-token-expiry.html).
    Falls back to a directly-pasted static_token if no refresh credentials are configured
    (fine for a quick manual test inside that token's 1-hour window, but it WILL 401 after
    that — the refresh-token path is what to use for anything that needs to stay live).

    Keep prompts small and tear the endpoint down when idle (budget guardrail).
    """

    def __init__(self, endpoint: str, org_id: str, model: str, accounts_url: str,
                 client_id: str = "", client_secret: str = "", refresh_token: str = "",
                 static_token: str = ""):
        self.endpoint = endpoint
        self.org_id = org_id
        self.model = model
        self.accounts_url = accounts_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self._cached_token = static_token
        self._cached_token_expiry = 0.0  # epoch seconds; 0 forces a refresh on first use

    def _access_token(self) -> str:
        """Return a live access token, auto-refreshing via the refresh token when
        configured. Without refresh credentials, just returns whatever static token was
        passed in (may already be stale — that's the caller's problem in that mode)."""
        if not (self.client_id and self.client_secret and self.refresh_token):
            return self._cached_token
        import time
        if self._cached_token and time.time() < self._cached_token_expiry:
            return self._cached_token
        import httpx
        resp = httpx.post(self.accounts_url, params={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        self._cached_token = data["access_token"]
        self._cached_token_expiry = time.time() + data.get("expires_in", 3600) - 60
        return self._cached_token

    def complete(self, prompt: str, context: list[str] | None = None) -> LLMResult:
        """POST to a Catalyst QuickML LLM Serving endpoint (RAG-grounded on context
        we retrieve ourselves from the FIR case view — see services/mo.py / assistant
        router — rather than QuickML's own Knowledge Base, since that's a static
        document-upload store and our case data is live/queryable already).

        Not runnable locally — use LLM_PROVIDER=mock for dev."""
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
            "stream": False,
        }
        headers = {
            "Authorization": f"Zoho-oauthtoken {self._access_token()}",
            "CATALYST-ORG": self.org_id,
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=25) as client:
            resp = client.post(self.endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        # tolerate OpenAI-style, {output/text}, or QuickML-prediction-style shapes
        text = (
            (data.get("choices", [{}])[0].get("message", {}) or {}).get("content")
            or data.get("output")
            or data.get("text")
            or data.get("prediction")
            or ""
        ).strip()
        return LLMResult(text=text, provider="quickml", model=self.model, grounded_on=ctx[:5])


@lru_cache
def get_llm() -> LLMProvider:
    s = get_settings()
    if s.llm_provider == "quickml":
        missing = [name for name, val in [
            ("QUICKML_ENDPOINT", s.quickml_endpoint),
            ("QUICKML_ORG_ID", s.quickml_org_id),
        ] if not val]
        # Auth: prefer the refresh-token trio (auto-renews, never goes stale); fall back
        # to a directly-pasted static access token (expires in 1hr — fine for a quick test).
        has_refresh = bool(s.quickml_client_id and s.quickml_client_secret and s.quickml_refresh_token)
        has_static = bool(s.quickml_oauth_token)
        if not (has_refresh or has_static):
            missing.append(
                "QUICKML_CLIENT_ID+QUICKML_CLIENT_SECRET+QUICKML_REFRESH_TOKEN "
                "(or QUICKML_OAUTH_TOKEN for a short-lived static test)"
            )
        if missing:
            # Fail open to mock rather than construct a provider that will 401/404 on
            # first real request — LLM_PROVIDER=quickml with incomplete config is a
            # setup-in-progress state, not a reason to break the app.
            print(f"[llm] LLM_PROVIDER=quickml but missing {missing} — falling back to mock")
            return MockProvider()
        return QuickMLProvider(
            endpoint=s.quickml_endpoint,
            org_id=s.quickml_org_id,
            model=s.quickml_model,
            accounts_url=s.quickml_accounts_url,
            client_id=s.quickml_client_id,
            client_secret=s.quickml_client_secret,
            refresh_token=s.quickml_refresh_token,
            static_token=s.quickml_oauth_token,
        )
    return MockProvider()
