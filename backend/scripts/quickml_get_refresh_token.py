"""
One-time helper: exchange a Self Client authorization CODE for a QuickML refresh token,
so you never have to hand-craft the curl request or re-generate tokens by hand.

The code itself still has to come from a human click — Zoho requires that as the actual
consent step (api-console.zoho.com -> Self Client -> Generate Code tab, scope
QuickML.deployment.READ). It's only valid for a few minutes, so run this script right
after copying it. Everything after that (the exchange, and every future access-token
refresh) is handled in code — see backend/app/services/llm.py::QuickMLProvider.

Usage:
    python backend/scripts/quickml_get_refresh_token.py \
        --client-id 1000.XXXX --client-secret xxxx --code 1000.yyyy.zzzz

    # also write the three values straight into backend/.env:
    python backend/scripts/quickml_get_refresh_token.py \
        --client-id 1000.XXXX --client-secret xxxx --code 1000.yyyy.zzzz --write-env

Reference: https://www.zoho.com/accounts/protocol/oauth/self-client/authorization-code-flow.html
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--client-id", required=True, help="From Self Client -> Client Secret tab")
    p.add_argument("--client-secret", required=True, help="From Self Client -> Client Secret tab")
    p.add_argument("--code", required=True, help="The short-lived code from the Generate Code tab")
    p.add_argument("--accounts-url", default="https://accounts.zoho.in/oauth/v2/token",
                    help="Datacenter-specific accounts server (default: India DC)")
    p.add_argument("--write-env", action="store_true",
                    help="Also write CLIENT_ID/CLIENT_SECRET/REFRESH_TOKEN into backend/.env")
    args = p.parse_args()

    import httpx

    try:
        resp = httpx.post(args.accounts_url, params={
            "client_id": args.client_id,
            "client_secret": args.client_secret,
            "grant_type": "authorization_code",
            "code": args.code,
        }, timeout=15)
    except Exception as e:
        print(f"Could not reach {args.accounts_url}: {e}", file=sys.stderr)
        return 1

    if resp.status_code != 200:
        print(f"Exchange failed: HTTP {resp.status_code}\n{resp.text}", file=sys.stderr)
        print(
            "\nCommon causes: the code already expired (~3 min lifetime — generate a fresh "
            "one and rerun immediately), or it was already used once (codes are single-use).",
            file=sys.stderr,
        )
        return 1

    data = resp.json()
    refresh_token = data.get("refresh_token")
    access_token = data.get("access_token")
    if not refresh_token:
        print(f"No refresh_token in response — full body:\n{data}", file=sys.stderr)
        return 1

    print("Exchange succeeded.")
    print(f"  access_token  (expires in {data.get('expires_in', '?')}s): {access_token}")
    print(f"  refresh_token (never expires): {refresh_token}")

    if args.write_env:
        env_path = Path(__file__).resolve().parent.parent / ".env"
        if not env_path.exists():
            print(f"\n{env_path} doesn't exist yet — create it from ../.env.example first.", file=sys.stderr)
            return 1
        text = env_path.read_text()

        def set_kv(text: str, key: str, value: str) -> str:
            pattern = rf"^{key}=.*$"
            line = f"{key}={value}"
            if re.search(pattern, text, flags=re.MULTILINE):
                return re.sub(pattern, line, text, flags=re.MULTILINE)
            return text.rstrip("\n") + f"\n{line}\n"

        text = set_kv(text, "QUICKML_CLIENT_ID", args.client_id)
        text = set_kv(text, "QUICKML_CLIENT_SECRET", args.client_secret)
        text = set_kv(text, "QUICKML_REFRESH_TOKEN", refresh_token)
        env_path.write_text(text)
        print(f"\nWrote QUICKML_CLIENT_ID / QUICKML_CLIENT_SECRET / QUICKML_REFRESH_TOKEN to {env_path}")
        print("Set LLM_PROVIDER=quickml there too (still 'mock' by default) and restart uvicorn.")
    else:
        print("\nPaste these into backend/.env as QUICKML_CLIENT_ID / QUICKML_CLIENT_SECRET / "
              "QUICKML_REFRESH_TOKEN (or rerun with --write-env to do it automatically).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
