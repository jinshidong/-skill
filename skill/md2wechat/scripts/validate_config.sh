#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="__REPO_ROOT__"
PYTHON_BIN="$REPO_ROOT/.venv/bin/python"

"$PYTHON_BIN" - <<'PY'
import json
import os
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

appid = os.getenv("WECHAT_APPID", "").strip()
secret = os.getenv("WECHAT_SECRET", "").strip()

def fetch_public_ip(url: str) -> str:
    try:
        with urlopen(url, timeout=10) as resp:
            return resp.read().decode("utf-8").strip()
    except Exception:
        return ""

public_ip = fetch_public_ip("https://api.ipify.org") or fetch_public_ip("https://ifconfig.me/ip")

result = {
    "wechat_appid_set": bool(appid),
    "wechat_secret_set": bool(secret),
    "public_ip": public_ip,
    "wechat_token_check": "skipped",
}

if not appid or not secret:
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0)

payload = json.dumps(
    {
        "grant_type": "client_credential",
        "appid": appid,
        "secret": secret,
        "force_refresh": False,
    },
    ensure_ascii=False,
).encode("utf-8")

req = Request(
    "https://api.weixin.qq.com/cgi-bin/stable_token",
    data=payload,
    headers={"Content-Type": "application/json; charset=utf-8"},
    method="POST",
)

try:
    with urlopen(req, timeout=20) as resp:
        body = resp.read().decode("utf-8")
        data = json.loads(body)
except HTTPError as exc:
    body = exc.read().decode("utf-8", errors="replace")
    try:
        data = json.loads(body)
    except Exception:
        data = {"http_error": exc.code, "body": body}
except URLError as exc:
    result["wechat_token_check"] = "network_error"
    result["wechat_token_error"] = str(exc)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0)

if "access_token" in data:
    result["wechat_token_check"] = "ok"
elif data.get("errcode") == 40164:
    result["wechat_token_check"] = "invalid_ip_not_in_whitelist"
    result["wechat_token_error"] = data.get("errmsg", "")
elif data.get("errcode") is not None:
    result["wechat_token_check"] = "api_error"
    result["wechat_token_error"] = data.get("errmsg", "")
    result["wechat_errcode"] = data.get("errcode")
else:
    result["wechat_token_check"] = "unexpected_response"
    result["wechat_token_error"] = data

print(json.dumps(result, ensure_ascii=False, indent=2))
PY
