#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MD2WeChat 多公众号池与草稿投递服务。

使用 Flask + sqlite3 提供一个轻量后台：
- `/accounts` 管理公众号账号池
- `/jobs` 查看投递历史并手动重试
- `/api/drafts` 供 OpenClaw / Telegram 直接提交本地 Markdown 草稿
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

try:
    from md2wechat import MarkdownParser, STYLES
    from md2wechat_config import resolve_publish_article_path
    from wechat_draft_api import (
        DraftValidationError,
        WeChatAPIError,
        WeChatDraftClient,
        create_draft_from_markdown,
    )
except ImportError:
    from .md2wechat import MarkdownParser, STYLES
    from .md2wechat_config import resolve_publish_article_path
    from .wechat_draft_api import (
        DraftValidationError,
        WeChatAPIError,
        WeChatDraftClient,
        create_draft_from_markdown,
    )


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = REPO_ROOT / "data" / "md2wechat_multiuser.sqlite"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 1024
FLASH_SECRET = "md2wechat-multi-account-admin"
RISK_WARNING = (
    "风险警告：当前管理台无登录、无鉴权，且 SQLite 中以明文保存 AppSecret。"
    "任何能访问当前服务端口的人都可以查看账号、修改配置并立即创建真实微信草稿。"
)

JOB_STATUS_PROCESSING = "processing"
JOB_STATUS_SUCCESS = "success"
JOB_STATUS_FAILED = "failed"
JOB_STATUS_REJECTED = "rejected"

ACCOUNT_COLUMNS = (
    "id",
    "alias",
    "wechat_appid",
    "wechat_app_secret",
    "public_name",
    "description",
    "enabled",
    "created_at",
    "updated_at",
)

JOB_COLUMNS = (
    "id",
    "account_alias",
    "article_path",
    "source",
    "origin_chat_id",
    "origin_message_id",
    "request_text",
    "status",
    "title",
    "media_id",
    "thumb_media_id",
    "error_message",
    "created_at",
    "finished_at",
)


@dataclass(frozen=True)
class DraftRequest:
    account_alias: str
    article_path: str
    source: str
    origin_chat_id: str = ""
    origin_message_id: str = ""
    request_text: str = ""
    style: str = ""
    cover_path: str = ""
    author: str = ""
    digest: str = ""
    source_url: str = ""


class MultiAccountStore:
    """SQLite 存储层"""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def init_db(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS wechat_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alias TEXT NOT NULL UNIQUE,
            wechat_appid TEXT NOT NULL,
            wechat_app_secret TEXT NOT NULL,
            public_name TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS draft_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_alias TEXT NOT NULL,
            article_path TEXT NOT NULL,
            source TEXT NOT NULL,
            origin_chat_id TEXT NOT NULL DEFAULT '',
            origin_message_id TEXT NOT NULL DEFAULT '',
            request_text TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            media_id TEXT NOT NULL DEFAULT '',
            thumb_media_id TEXT NOT NULL DEFAULT '',
            error_message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            finished_at TEXT NOT NULL DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_wechat_accounts_alias ON wechat_accounts(alias);
        CREATE INDEX IF NOT EXISTS idx_wechat_accounts_enabled ON wechat_accounts(enabled);
        CREATE INDEX IF NOT EXISTS idx_draft_jobs_account_alias ON draft_jobs(account_alias);
        CREATE INDEX IF NOT EXISTS idx_draft_jobs_status ON draft_jobs(status);
        CREATE INDEX IF NOT EXISTS idx_draft_jobs_created_at ON draft_jobs(created_at DESC);
        """
        with self.connect() as connection:
            connection.executescript(schema)

    def list_accounts(self) -> List[Dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM wechat_accounts ORDER BY enabled DESC, alias ASC"
            ).fetchall()
        return [self._account_row_to_dict(row) for row in rows]

    def list_enabled_aliases(self) -> List[str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT alias FROM wechat_accounts WHERE enabled = 1 ORDER BY alias ASC"
            ).fetchall()
        return [str(row["alias"]) for row in rows]

    def get_account_by_id(self, account_id: int) -> Optional[Dict[str, Any]]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM wechat_accounts WHERE id = ?",
                (account_id,),
            ).fetchone()
        return self._account_row_to_dict(row) if row else None

    def get_account_by_alias(self, alias: str) -> Optional[Dict[str, Any]]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM wechat_accounts WHERE alias = ?",
                (alias,),
            ).fetchone()
        return self._account_row_to_dict(row) if row else None

    def create_account(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        normalized = normalize_account_payload(payload)
        now = now_string()
        try:
            with self.connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO wechat_accounts (
                        alias,
                        wechat_appid,
                        wechat_app_secret,
                        public_name,
                        description,
                        enabled,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized["alias"],
                        normalized["wechat_appid"],
                        normalized["wechat_app_secret"],
                        normalized["public_name"],
                        normalized["description"],
                        1 if normalized["enabled"] else 0,
                        now,
                        now,
                    ),
                )
                account_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"alias 已存在: {normalized['alias']}") from exc
        return self.get_account_by_id(account_id) or {}

    def update_account(self, account_id: int, payload: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        normalized = normalize_account_payload(payload)
        now = now_string()
        try:
            with self.connect() as connection:
                cursor = connection.execute(
                    """
                    UPDATE wechat_accounts
                    SET alias = ?,
                        wechat_appid = ?,
                        wechat_app_secret = ?,
                        public_name = ?,
                        description = ?,
                        enabled = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        normalized["alias"],
                        normalized["wechat_appid"],
                        normalized["wechat_app_secret"],
                        normalized["public_name"],
                        normalized["description"],
                        1 if normalized["enabled"] else 0,
                        now,
                        account_id,
                    ),
                )
                if cursor.rowcount == 0:
                    return None
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"alias 已存在: {normalized['alias']}") from exc
        return self.get_account_by_id(account_id)

    def delete_account(self, account_id: int) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM wechat_accounts WHERE id = ?",
                (account_id,),
            )
        return cursor.rowcount > 0

    def create_job(
        self,
        *,
        account_alias: str,
        article_path: str,
        source: str,
        origin_chat_id: str,
        origin_message_id: str,
        request_text: str,
        status: str,
        title: str = "",
    ) -> int:
        now = now_string()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO draft_jobs (
                    account_alias,
                    article_path,
                    source,
                    origin_chat_id,
                    origin_message_id,
                    request_text,
                    status,
                    title,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    account_alias,
                    article_path,
                    source,
                    origin_chat_id,
                    origin_message_id,
                    request_text,
                    status,
                    title,
                    now,
                ),
            )
        return int(cursor.lastrowid)

    def mark_job_success(
        self,
        job_id: int,
        *,
        status: str,
        title: str,
        media_id: str,
        thumb_media_id: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE draft_jobs
                SET status = ?,
                    title = ?,
                    media_id = ?,
                    thumb_media_id = ?,
                    error_message = '',
                    finished_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    title,
                    media_id,
                    thumb_media_id,
                    now_string(),
                    job_id,
                ),
            )

    def mark_job_failed(
        self,
        job_id: int,
        *,
        status: str,
        error_message: str,
        title: str = "",
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE draft_jobs
                SET status = ?,
                    title = CASE WHEN ? != '' THEN ? ELSE title END,
                    error_message = ?,
                    finished_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    title,
                    title,
                    error_message,
                    now_string(),
                    job_id,
                ),
            )

    def list_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM draft_jobs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._job_row_to_dict(row) for row in rows]

    def get_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM draft_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        return self._job_row_to_dict(row) if row else None

    @staticmethod
    def _account_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": int(row["id"]),
            "alias": str(row["alias"]),
            "wechat_appid": str(row["wechat_appid"]),
            "wechat_app_secret": str(row["wechat_app_secret"]),
            "public_name": str(row["public_name"]),
            "description": str(row["description"]),
            "enabled": bool(row["enabled"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }

    @staticmethod
    def _job_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": int(row["id"]),
            "account_alias": str(row["account_alias"]),
            "article_path": str(row["article_path"]),
            "source": str(row["source"]),
            "origin_chat_id": str(row["origin_chat_id"]),
            "origin_message_id": str(row["origin_message_id"]),
            "request_text": str(row["request_text"]),
            "status": str(row["status"]),
            "title": str(row["title"]),
            "media_id": str(row["media_id"]),
            "thumb_media_id": str(row["thumb_media_id"]),
            "error_message": str(row["error_message"]),
            "created_at": str(row["created_at"]),
            "finished_at": str(row["finished_at"]),
        }


def normalize_string(value: Any) -> str:
    return str(value or "").strip()


def normalize_boolean(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    normalized = normalize_string(value).lower()
    if not normalized:
        return default
    if normalized in {"1", "true", "yes", "on", "enabled"}:
        return True
    if normalized in {"0", "false", "no", "off", "disabled"}:
        return False
    return default


def now_string() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def validate_alias(raw_alias: Any) -> str:
    alias = normalize_string(raw_alias)
    if not alias:
        raise ValueError("alias 不能为空")
    if any(char.isspace() for char in alias):
        raise ValueError("alias 不能包含空白字符")
    if len(alias) > 64:
        raise ValueError("alias 长度不能超过 64 个字符")
    return alias


def normalize_account_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "alias": validate_alias(payload.get("alias")),
        "wechat_appid": require_value(payload.get("wechat_appid"), "wechat_appid 不能为空"),
        "wechat_app_secret": require_value(payload.get("wechat_app_secret"), "wechat_app_secret 不能为空"),
        "public_name": normalize_string(payload.get("public_name")),
        "description": normalize_string(payload.get("description")),
        "enabled": normalize_boolean(payload.get("enabled"), default=False),
    }


def require_value(value: Any, error_message: str) -> str:
    normalized = normalize_string(value)
    if not normalized:
        raise ValueError(error_message)
    return normalized


def normalize_draft_request(payload: Mapping[str, Any]) -> DraftRequest:
    style = normalize_string(payload.get("style"))
    if style and style not in STYLES:
        raise ValueError(f"未知的 style: {style}")

    return DraftRequest(
        account_alias=validate_alias(payload.get("account_alias")),
        article_path=require_value(payload.get("article_path"), "article_path 不能为空"),
        source=require_value(payload.get("source"), "source 不能为空"),
        origin_chat_id=normalize_string(payload.get("origin_chat_id")),
        origin_message_id=normalize_string(payload.get("origin_message_id")),
        request_text=normalize_string(payload.get("request_text")),
        style=style,
        cover_path=normalize_string(payload.get("cover_path") or payload.get("cover_image_path")),
        author=normalize_string(payload.get("author")),
        digest=normalize_string(payload.get("digest")),
        source_url=normalize_string(payload.get("source_url") or payload.get("content_source_url")),
    )


def resolve_request_article_path(article_path: str) -> Tuple[str, Optional[Path], Optional[str]]:
    requested = Path(article_path).expanduser().resolve()
    try:
        publish_path = resolve_publish_article_path(requested)
    except ValueError as exc:
        return str(requested), None, str(exc)
    return str(publish_path), publish_path, None


def extract_best_effort_title(article_path: Optional[Path]) -> str:
    if article_path is None or not article_path.exists() or article_path.suffix != ".md":
        return ""
    try:
        parser = MarkdownParser(article_path.read_text(encoding="utf-8"))
        return normalize_string(parser.get_title())
    except Exception:
        return ""


def serialize_request_context(draft_request: DraftRequest) -> str:
    overrides = {
        "style": draft_request.style,
        "cover_path": draft_request.cover_path,
        "author": draft_request.author,
        "digest": draft_request.digest,
        "source_url": draft_request.source_url,
    }
    compact_overrides = {key: value for key, value in overrides.items() if value}
    if not compact_overrides:
        return draft_request.request_text
    return json.dumps(
        {
            "request_text": draft_request.request_text,
            "overrides": compact_overrides,
        },
        ensure_ascii=False,
    )


def parse_request_context(raw_value: str) -> Tuple[str, Dict[str, str]]:
    text = normalize_string(raw_value)
    if not text:
        return "", {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text, {}
    if not isinstance(data, dict):
        return text, {}
    request_text = normalize_string(data.get("request_text"))
    overrides = data.get("overrides")
    if not isinstance(overrides, dict):
        return request_text or text, {}
    normalized_overrides = {
        str(key): normalize_string(value)
        for key, value in overrides.items()
        if normalize_string(value)
    }
    return request_text, normalized_overrides


def summarize_overrides(overrides: Mapping[str, str]) -> str:
    parts: List[str] = []
    for key in ("style", "cover_path", "author", "digest", "source_url"):
        value = normalize_string(overrides.get(key))
        if value:
            parts.append(f"{key}={value}")
    return " | ".join(parts)


def build_draft_response(
    *,
    ok: bool,
    status: str,
    account_alias: str,
    title: str = "",
    job_id: Optional[int] = None,
    media_id: str = "",
    thumb_media_id: str = "",
    error: str = "",
    available_aliases: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "ok": ok,
        "job_id": job_id,
        "status": status,
        "account_alias": account_alias,
        "title": title,
        "media_id": media_id,
        "thumb_media_id": thumb_media_id,
        "error": error,
    }
    if available_aliases is not None:
        payload["available_aliases"] = list(available_aliases)
    return payload


def status_code_for_value_error(exc: ValueError) -> int:
    return 409 if "alias 已存在" in str(exc) else 400


def invoke_publisher(
    publisher: Callable[..., Dict[str, Any]],
    draft_request: DraftRequest,
    account: Mapping[str, Any],
    article_path: str,
) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {
        "client": WeChatDraftClient(
            appid=str(account["wechat_appid"]),
            secret=str(account["wechat_app_secret"]),
        )
    }
    if draft_request.style:
        kwargs["style"] = draft_request.style
    if draft_request.cover_path:
        kwargs["cover_image_path"] = draft_request.cover_path
    if draft_request.author:
        kwargs["author"] = draft_request.author
    if draft_request.digest:
        kwargs["digest"] = draft_request.digest
    if draft_request.source_url:
        kwargs["content_source_url"] = draft_request.source_url
    return publisher(article_path, **kwargs)


def submit_draft_job(
    store: MultiAccountStore,
    publisher: Callable[..., Dict[str, Any]],
    draft_request: DraftRequest,
) -> Tuple[Dict[str, Any], int]:
    enabled_aliases = store.list_enabled_aliases()
    account = store.get_account_by_alias(draft_request.account_alias)
    if account is None:
        return (
            build_draft_response(
                ok=False,
                status=JOB_STATUS_REJECTED,
                account_alias=draft_request.account_alias,
                error=f"公众号 alias 不存在: {draft_request.account_alias}",
                available_aliases=enabled_aliases,
            ),
            404,
        )
    if not account["enabled"]:
        return (
            build_draft_response(
                ok=False,
                status=JOB_STATUS_REJECTED,
                account_alias=draft_request.account_alias,
                error=f"公众号账号已禁用，无法投递: {draft_request.account_alias}",
                available_aliases=enabled_aliases,
            ),
            409,
        )

    resolved_article_path, publish_path, resolve_error = resolve_request_article_path(draft_request.article_path)
    title_hint = extract_best_effort_title(publish_path)
    job_id = store.create_job(
        account_alias=draft_request.account_alias,
        article_path=resolved_article_path,
        source=draft_request.source,
        origin_chat_id=draft_request.origin_chat_id,
        origin_message_id=draft_request.origin_message_id,
        request_text=serialize_request_context(draft_request),
        status=JOB_STATUS_PROCESSING,
        title=title_hint,
    )

    if resolve_error:
        store.mark_job_failed(
            job_id,
            status=JOB_STATUS_FAILED,
            title=title_hint,
            error_message=resolve_error,
        )
        return (
            build_draft_response(
                ok=False,
                status=JOB_STATUS_FAILED,
                account_alias=draft_request.account_alias,
                title=title_hint,
                job_id=job_id,
                error=resolve_error,
            ),
            400,
        )

    try:
        result = invoke_publisher(
            publisher,
            draft_request,
            account,
            resolved_article_path,
        )
    except DraftValidationError as exc:
        message = str(exc)
        store.mark_job_failed(
            job_id,
            status=JOB_STATUS_FAILED,
            title=title_hint,
            error_message=message,
        )
        return (
            build_draft_response(
                ok=False,
                status=JOB_STATUS_FAILED,
                account_alias=draft_request.account_alias,
                title=title_hint,
                job_id=job_id,
                error=message,
            ),
            400,
        )
    except WeChatAPIError as exc:
        message = str(exc)
        store.mark_job_failed(
            job_id,
            status=JOB_STATUS_FAILED,
            title=title_hint,
            error_message=message,
        )
        return (
            build_draft_response(
                ok=False,
                status=JOB_STATUS_FAILED,
                account_alias=draft_request.account_alias,
                title=title_hint,
                job_id=job_id,
                error=message,
            ),
            502,
        )
    except Exception as exc:  # pragma: no cover - 服务兜底
        message = f"未知错误: {exc}"
        store.mark_job_failed(
            job_id,
            status=JOB_STATUS_FAILED,
            title=title_hint,
            error_message=message,
        )
        return (
            build_draft_response(
                ok=False,
                status=JOB_STATUS_FAILED,
                account_alias=draft_request.account_alias,
                title=title_hint,
                job_id=job_id,
                error=message,
            ),
            500,
        )

    title = normalize_string(result.get("title")) or title_hint
    media_id = normalize_string(result.get("media_id"))
    thumb_media_id = normalize_string(result.get("thumb_media_id"))
    store.mark_job_success(
        job_id,
        status=normalize_string(result.get("status")) or JOB_STATUS_SUCCESS,
        title=title,
        media_id=media_id,
        thumb_media_id=thumb_media_id,
    )
    return (
        build_draft_response(
            ok=True,
            status=JOB_STATUS_SUCCESS,
            account_alias=draft_request.account_alias,
            title=title,
            job_id=job_id,
            media_id=media_id,
            thumb_media_id=thumb_media_id,
            error="",
        ),
        200,
    )


def get_payload() -> Dict[str, Any]:
    if request.is_json:
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else {}
    return request.form.to_dict()


def load_jobs_for_view(store: MultiAccountStore) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    accounts_by_alias = {account["alias"]: account for account in store.list_accounts()}
    jobs = store.list_jobs()
    counters = {
        JOB_STATUS_SUCCESS: 0,
        JOB_STATUS_FAILED: 0,
        JOB_STATUS_PROCESSING: 0,
    }
    for job in jobs:
        request_text, overrides = parse_request_context(job["request_text"])
        job["display_request_text"] = request_text
        job["display_overrides"] = summarize_overrides(overrides)
        account = accounts_by_alias.get(job["account_alias"])
        job["retry_allowed"] = bool(account and account["enabled"])
        if not account:
            job["retry_hint"] = "账号已删除，无法重试"
        elif not account["enabled"]:
            job["retry_hint"] = "账号已禁用，无法重试"
        else:
            job["retry_hint"] = "将立即再次推送微信草稿箱"
        if job["status"] in counters:
            counters[job["status"]] += 1
    return jobs, counters


def build_retry_request(job: Mapping[str, Any]) -> DraftRequest:
    request_text, overrides = parse_request_context(str(job["request_text"]))
    return DraftRequest(
        account_alias=str(job["account_alias"]),
        article_path=str(job["article_path"]),
        source=str(job["source"]),
        origin_chat_id=str(job["origin_chat_id"]),
        origin_message_id=str(job["origin_message_id"]),
        request_text=request_text,
        style=normalize_string(overrides.get("style")),
        cover_path=normalize_string(overrides.get("cover_path")),
        author=normalize_string(overrides.get("author")),
        digest=normalize_string(overrides.get("digest")),
        source_url=normalize_string(overrides.get("source_url")),
    )


def create_app(
    *,
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    publisher: Callable[..., Dict[str, Any]] = create_draft_from_markdown,
) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(REPO_ROOT / "templates"),
    )
    app.secret_key = FLASH_SECRET

    store = MultiAccountStore(database_path)
    app.config["MD2WECHAT_MULTIUSER_DB_PATH"] = str(store.database_path)
    app.config["MD2WECHAT_MULTIUSER_STORE"] = store
    app.config["MD2WECHAT_MULTIUSER_PUBLISHER"] = publisher
    app.config["MD2WECHAT_STYLE_NAMES"] = sorted(STYLES.keys())

    @app.context_processor
    def inject_shared_context() -> Dict[str, Any]:
        return {
            "risk_warning": RISK_WARNING,
        }

    @app.get("/")
    def index() -> Any:
        return redirect(url_for("accounts_page"))

    @app.get("/accounts")
    def accounts_page() -> Any:
        return render_template(
            "accounts.html",
            page_title="公众号账号池",
            accounts=store.list_accounts(),
            database_path=str(store.database_path),
        )

    @app.post("/accounts/create")
    def accounts_page_create() -> Any:
        try:
            account = store.create_account(get_payload())
        except ValueError as exc:
            flash(str(exc), "error")
        else:
            flash(f"账号已创建: {account['alias']}", "success")
        return redirect(url_for("accounts_page"))

    @app.post("/accounts/<int:account_id>/update")
    def accounts_page_update(account_id: int) -> Any:
        try:
            account = store.update_account(account_id, get_payload())
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("accounts_page"))
        if account is None:
            flash(f"账号不存在: #{account_id}", "error")
        else:
            flash(f"账号已更新: {account['alias']}", "success")
        return redirect(url_for("accounts_page"))

    @app.post("/accounts/<int:account_id>/delete")
    def accounts_page_delete(account_id: int) -> Any:
        if store.delete_account(account_id):
            flash(f"账号已删除: #{account_id}", "success")
        else:
            flash(f"账号不存在: #{account_id}", "error")
        return redirect(url_for("accounts_page"))

    @app.get("/jobs")
    def jobs_page() -> Any:
        jobs, counters = load_jobs_for_view(store)
        return render_template(
            "jobs.html",
            page_title="草稿投递历史",
            jobs=jobs,
            counters=counters,
        )

    @app.post("/jobs/<int:job_id>/retry")
    def retry_job(job_id: int) -> Any:
        job = store.get_job(job_id)
        if job is None:
            flash(f"任务不存在: #{job_id}", "error")
            return redirect(url_for("jobs_page"))
        result, status_code = submit_draft_job(
            store,
            publisher,
            build_retry_request(job),
        )
        if status_code == 200:
            flash(
                f"重试成功，新任务 #{result['job_id']} 已创建，media_id={result['media_id']}",
                "success",
            )
        else:
            flash(
                f"重试失败: {result['error']}",
                "error",
            )
        return redirect(url_for("jobs_page"))

    @app.get("/api/accounts")
    def list_accounts_api() -> Any:
        return jsonify({"ok": True, "accounts": store.list_accounts()})

    @app.post("/api/accounts")
    def create_account_api() -> Any:
        try:
            account = store.create_account(get_payload())
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), status_code_for_value_error(exc)
        return jsonify({"ok": True, "account": account}), 201

    @app.put("/api/accounts/<int:account_id>")
    def update_account_api(account_id: int) -> Any:
        try:
            account = store.update_account(account_id, get_payload())
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), status_code_for_value_error(exc)
        if account is None:
            return jsonify({"ok": False, "error": f"账号不存在: #{account_id}"}), 404
        return jsonify({"ok": True, "account": account})

    @app.delete("/api/accounts/<int:account_id>")
    def delete_account_api(account_id: int) -> Any:
        if not store.delete_account(account_id):
            return jsonify({"ok": False, "error": f"账号不存在: #{account_id}"}), 404
        return jsonify({"ok": True, "deleted_id": account_id})

    @app.post("/api/drafts")
    def create_draft_api() -> Any:
        payload = get_payload()
        try:
            draft_request = normalize_draft_request(payload)
        except ValueError as exc:
            return (
                jsonify(
                    build_draft_response(
                        ok=False,
                        status=JOB_STATUS_REJECTED,
                        account_alias=normalize_string(payload.get("account_alias")),
                        error=str(exc),
                        available_aliases=store.list_enabled_aliases(),
                    )
                ),
                400,
            )
        response_payload, status_code = submit_draft_job(store, publisher, draft_request)
        return jsonify(response_payload), status_code

    return app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="启动 MD2WeChat 多公众号池后台服务")
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"监听地址，默认 {DEFAULT_HOST}",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"监听端口，默认 {DEFAULT_PORT}",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DATABASE_PATH),
        help=f"SQLite 数据库路径，默认 {DEFAULT_DATABASE_PATH}",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="开启 Flask debug 模式",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    app = create_app(database_path=args.db)
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
