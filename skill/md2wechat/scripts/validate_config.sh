#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/resolve_repo_root.sh"
REPO_ROOT="$(resolve_md2wechat_repo_root)"
PYTHON_BIN="$REPO_ROOT/.venv/bin/python"

"$PYTHON_BIN" - <<'PY' "$REPO_ROOT"
import json
import sys
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from pathlib import Path

repo_root = Path(sys.argv[1])
sys.path.insert(0, str(repo_root / "src"))

from md2wechat_config import load_md2wechat_config, resolve_wechat_credentials

runtime_config = load_md2wechat_config()
credentials = resolve_wechat_credentials(runtime_config)
appid = credentials.appid
secret = credentials.secret

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
    "credential_source": credentials.source,
    "config_path": str(runtime_config.path),
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
