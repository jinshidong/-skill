#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MD2WeChat runtime config and path resolution helpers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

import yaml


DEFAULT_AUTHOR_NAME = "路人甲"
DEFAULT_CAMERA_READY_STYLE = "viral-writer-wechat"
DEFAULT_CONFIG_PATH = Path.home() / ".config" / "md2wechat" / "config.yaml"


@dataclass(frozen=True)
class Md2WeChatConfig:
    path: Path
    raw: Dict[str, Any]


@dataclass(frozen=True)
class ResolvedCredentials:
    appid: str
    secret: str
    source: str


@dataclass(frozen=True)
class ResolvedValue:
    value: str
    source: str


def _normalize_string(value: Any) -> str:
    return str(value or "").strip()


def _ensure_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    normalized = _normalize_string(value).lower()
    if not normalized:
        return default
    if normalized in {"1", "true", "yes", "on", "enabled"}:
        return True
    if normalized in {"0", "false", "no", "off", "disabled"}:
        return False
    return default


def load_md2wechat_config(config_path: Optional[str] = None) -> Md2WeChatConfig:
    path = Path(config_path).expanduser() if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        return Md2WeChatConfig(path=path, raw={})

    raw = path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw) or {}
    if not isinstance(parsed, dict):
        raise ValueError(f"配置文件顶层必须是映射: {path}")

    return Md2WeChatConfig(path=path, raw=parsed)


def get_article_defaults(config: Optional[Md2WeChatConfig] = None) -> Dict[str, str]:
    runtime_config = config or load_md2wechat_config()
    defaults = _ensure_dict(runtime_config.raw.get("article_defaults"))
    return {
        "author": _normalize_string(defaults.get("author")),
        "cover": _normalize_string(defaults.get("cover")),
        "digest": _normalize_string(defaults.get("digest")),
        "source": _normalize_string(defaults.get("source")),
        "source_url": _normalize_string(defaults.get("source_url")),
    }


def get_camera_ready_config(config: Optional[Md2WeChatConfig] = None) -> Dict[str, Any]:
    runtime_config = config or load_md2wechat_config()
    section = _ensure_dict(runtime_config.raw.get("camera_ready"))
    return {
        "enabled": _coerce_bool(section.get("enabled"), default=False),
        "style": _normalize_string(section.get("style")) or DEFAULT_CAMERA_READY_STYLE,
    }


def resolve_wechat_credentials(config: Optional[Md2WeChatConfig] = None) -> ResolvedCredentials:
    env_appid = _normalize_string(os.getenv("WECHAT_APPID"))
    env_secret = _normalize_string(os.getenv("WECHAT_SECRET"))
    if env_appid and env_secret:
        return ResolvedCredentials(appid=env_appid, secret=env_secret, source="env")

    runtime_config = config or load_md2wechat_config()
    wechat = _ensure_dict(runtime_config.raw.get("wechat"))
    config_appid = _normalize_string(wechat.get("appid"))
    config_secret = _normalize_string(wechat.get("secret"))
    if config_appid and config_secret:
        return ResolvedCredentials(appid=config_appid, secret=config_secret, source="config")

    return ResolvedCredentials(appid="", secret="", source="missing")


def resolve_value(
    cli_value: Optional[str],
    front_matter_value: Any,
    config_value: Any,
    fallback_value: Any = "",
) -> ResolvedValue:
    candidates = (
        ("cli", cli_value if cli_value is not None else ""),
        ("front_matter", front_matter_value),
        ("config", config_value),
        ("fallback", fallback_value),
    )
    for source, raw_value in candidates:
        normalized = _normalize_string(raw_value)
        if normalized:
            return ResolvedValue(value=normalized, source=source)
    return ResolvedValue(value="", source="missing")


def resolve_path_from_value(value: str, *, bases: Sequence[Path]) -> Path:
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()

    for base in bases:
        resolved = (Path(base).expanduser() / candidate).resolve()
        if resolved.exists():
            return resolved

    if bases:
        return (Path(bases[0]).expanduser() / candidate).resolve()
    return candidate.resolve()


def resolve_publish_article_path(article_path: str | Path) -> Path:
    requested = Path(article_path).expanduser().resolve()
    name = requested.name

    if name.endswith(".camera-ready.notes.md"):
        raise ValueError("请使用主稿 .camera-ready.md，而不是 .camera-ready.notes.md")
    if name.endswith(".camera-ready.md"):
        return requested
    if requested.suffix != ".md":
        return requested

    candidate = requested.with_name(f"{requested.stem}.camera-ready.md")
    if candidate.exists():
        return candidate
    return requested


def build_camera_ready_output_paths(article_path: str | Path) -> Tuple[Path, Path]:
    requested = Path(article_path).expanduser().resolve()
    name = requested.name

    if name.endswith(".camera-ready.notes.md"):
        base_name = name[: -len(".camera-ready.notes.md")]
    elif name.endswith(".camera-ready.md"):
        base_name = name[: -len(".camera-ready.md")]
    else:
        base_name = requested.stem

    parent = requested.parent
    return (
        parent / f"{base_name}.camera-ready.md",
        parent / f"{base_name}.camera-ready.notes.md",
    )
