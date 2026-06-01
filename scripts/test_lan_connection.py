#!/usr/bin/env python3
import argparse
import os
import sys
from typing import Any

import httpx


def _mask_proxy_env(value: str | None) -> str:
    if not value:
        return "<empty>"
    if "@" in value:
        return value.rsplit("@", 1)[-1]
    return value


def _request_json(base_url: str, path: str, trust_env: bool, timeout: float, api_key: str | None) -> tuple[bool, str, dict[str, Any] | None]:
    url = f"{base_url.rstrip('/')}{path}"
    headers: dict[str, str] = {}
    if api_key:
        headers["x-api-key"] = api_key

    try:
        with httpx.Client(timeout=timeout, trust_env=trust_env) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else None
            return True, f"HTTP {response.status_code}", payload
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}", None


def main() -> int:
    parser = argparse.ArgumentParser(description="Check LAN reachability for novel-tts service")
    parser.add_argument("--base-url", default="http://192.168.1.174:8008", help="Service base url")
    parser.add_argument("--timeout", type=float, default=8.0, help="Request timeout in seconds")
    parser.add_argument("--check-models", action="store_true", help="Also request /v1/models (requires --api-key)")
    parser.add_argument("--api-key", default=None, help="API key for /v1/models")
    args = parser.parse_args()

    print("== Proxy environment ==")
    print(f"ALL_PROXY={_mask_proxy_env(os.environ.get('ALL_PROXY') or os.environ.get('all_proxy'))}")
    print(f"HTTP_PROXY={_mask_proxy_env(os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy'))}")
    print(f"HTTPS_PROXY={_mask_proxy_env(os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy'))}")
    print(f"NO_PROXY={_mask_proxy_env(os.environ.get('NO_PROXY') or os.environ.get('no_proxy'))}")
    print()

    print("== /healthz ==")
    ok_env, msg_env, body_env = _request_json(args.base_url, "/healthz", trust_env=True, timeout=args.timeout, api_key=None)
    print(f"trust_env=True  -> {'OK' if ok_env else 'FAIL'} | {msg_env}")
    if body_env is not None:
        print(f"  body={body_env}")

    ok_noenv, msg_noenv, body_noenv = _request_json(args.base_url, "/healthz", trust_env=False, timeout=args.timeout, api_key=None)
    print(f"trust_env=False -> {'OK' if ok_noenv else 'FAIL'} | {msg_noenv}")
    if body_noenv is not None:
        print(f"  body={body_noenv}")

    if args.check_models:
        print()
        print("== /v1/models ==")
        ok_models_env, msg_models_env, body_models_env = _request_json(
            args.base_url,
            "/v1/models",
            trust_env=True,
            timeout=args.timeout,
            api_key=args.api_key,
        )
        print(f"trust_env=True  -> {'OK' if ok_models_env else 'FAIL'} | {msg_models_env}")
        if body_models_env is not None:
            print(f"  body={body_models_env}")

        ok_models_noenv, msg_models_noenv, body_models_noenv = _request_json(
            args.base_url,
            "/v1/models",
            trust_env=False,
            timeout=args.timeout,
            api_key=args.api_key,
        )
        print(f"trust_env=False -> {'OK' if ok_models_noenv else 'FAIL'} | {msg_models_noenv}")
        if body_models_noenv is not None:
            print(f"  body={body_models_noenv}")

    # return non-zero only if both modes fail healthz
    if not ok_env and not ok_noenv:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
