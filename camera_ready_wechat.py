#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Camera-ready bootstrapper for WeChat article drafts.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

src_path = str(Path(__file__).parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from md2wechat import MarkdownParser  # type: ignore
from md2wechat_config import (  # type: ignore
    DEFAULT_AUTHOR_NAME,
    build_camera_ready_output_paths,
    get_article_defaults,
    get_camera_ready_config,
    load_md2wechat_config,
    resolve_path_from_value,
    resolve_value,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="为微信公众号 reviewer 稿件生成 camera-ready 主稿与 notes",
    )
    parser.add_argument("md_file", help="输入 Markdown 文件路径")
    parser.add_argument("--title", help="覆盖终稿标题")
    parser.add_argument("--author", help="覆盖终稿作者")
    parser.add_argument("--digest", help="覆盖终稿摘要")
    parser.add_argument("--cover", help="覆盖终稿封面路径")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的 camera-ready 文件")
    return parser


def _dump_front_matter(data: dict[str, object]) -> str:
    lines = ["---"]
    for key, value in data.items():
        if value is None or value == "":
            continue
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
            continue
        escaped = str(value).replace('"', '\\"')
        lines.append(f'{key}: "{escaped}"')
    lines.append("---")
    return "\n".join(lines)


def _guess_cover_prompt(title: str, digest: str) -> str:
    focus = digest or title
    return (
        f"微信公众号封面，横版 2.35:1，突出《{title}》主题，"
        f"围绕“{focus[:48]}”构图，信息密度克制，适合在手机端首图使用，"
        "留出左侧或上方标题落字空间，整体风格干净、现代、可信。"
    )


def _build_alternative_titles(title: str) -> list[str]:
    base = title.strip() or "这篇文章值得认真看完"
    return [
        f"{base} — 策略：主标题延续",
        f"为什么说：{base} — 策略：好奇心缺口",
        f"{base}背后，真正变化的是什么？ — 策略：问题牵引",
        f"别只看热度，{base}才是关键 — 策略：反直觉",
        f"这一轮变化，不只是技术更新：{base} — 策略：趋势放大",
    ]


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.md_file).expanduser().resolve()
    if not input_path.exists():
        print(f"错误: Markdown 文件不存在: {input_path}")
        return 1

    camera_ready_path, notes_path = build_camera_ready_output_paths(input_path)
    if not args.force:
        for path in (camera_ready_path, notes_path):
            if path.exists():
                print(f"错误: 输出文件已存在，请使用 --force 覆盖: {path}")
                return 1

    runtime_config = load_md2wechat_config()
    article_defaults = get_article_defaults(runtime_config)
    camera_ready_config = get_camera_ready_config(runtime_config)

    raw = input_path.read_text(encoding="utf-8")
    parser = MarkdownParser(raw)
    fm = dict(parser.front_matter)

    resolved_title = resolve_value(args.title, fm.get("title", ""), "", "").value
    resolved_author = resolve_value(
        args.author,
        "",
        article_defaults.get("author", ""),
        DEFAULT_AUTHOR_NAME,
    ).value
    resolved_digest = resolve_value(
        args.digest,
        fm.get("digest", "") or fm.get("excerpt", "") or fm.get("summary", "") or fm.get("description", ""),
        article_defaults.get("digest", ""),
        "",
    ).value
    resolved_cover = resolve_value(
        args.cover,
        "",
        article_defaults.get("cover", ""),
        str(Path(__file__).resolve().parent / "examples" / "images" / "frontpage.png"),
    )

    resolved_cover_path = resolve_path_from_value(
        resolved_cover.value,
        bases=[runtime_config.path.parent, input_path.parent, Path.cwd()],
    )

    front_matter = {
        "title": resolved_title,
        "date": fm.get("date", ""),
        "author": resolved_author,
        "excerpt": resolved_digest,
        "permalink": fm.get("permalink", "") or article_defaults.get("source_url", ""),
        "cover": str(resolved_cover_path),
        "tags": fm.get("tags", []),
    }
    if article_defaults.get("source"):
        front_matter["source"] = article_defaults["source"]

    camera_ready_body = parser.body.strip()
    camera_ready_content = f"{_dump_front_matter(front_matter)}\n\n{camera_ready_body}\n"

    notes_lines = [
        f"# {camera_ready_path.stem} Notes",
        "",
        f"- 输入文件: `{input_path}`",
        f"- 输出主稿: `{camera_ready_path}`",
        f"- 输出说明: `{notes_path}`",
        f"- Camera-ready 风格: `{camera_ready_config['style']}`",
        "",
        "## 推荐摘要",
        "",
        resolved_digest or "请补一条适合公众号摘要的简介。",
        "",
        "## 备选标题",
        "",
    ]
    notes_lines.extend([f"{idx}. {title}" for idx, title in enumerate(_build_alternative_titles(resolved_title), start=1)])
    notes_lines.extend(
        [
            "",
            "## 配图指导",
            "",
            "### 封面图",
            "- 推荐比例: 2.35:1",
            f"- 生成 prompt: {_guess_cover_prompt(resolved_title, resolved_digest)}",
            "",
            "### 正文配图",
            "- 配图 1（开头后）: 用一张总览图建立主题氛围，避免过多细节。",
            f"- 配图 1 prompt: 围绕《{resolved_title}》的开篇主题做概念总览图，适合公众号正文插图。",
            "- 配图 2（中段核心论点后）: 强化关键趋势或对比关系。",
            f"- 配图 2 prompt: 用信息图或场景化插画呈现“{resolved_digest[:40] or resolved_title}”的关键变化。",
            "- 配图 3（结尾前）: 强化结论和行动感。",
            f"- 配图 3 prompt: 用克制、可信的视觉语言收束《{resolved_title}》的核心判断。",
        ]
    )

    camera_ready_path.write_text(camera_ready_content, encoding="utf-8")
    notes_path.write_text("\n".join(notes_lines).rstrip() + "\n", encoding="utf-8")

    print(f"✅ 已生成 camera-ready 主稿: {camera_ready_path}")
    print(f"✅ 已生成 camera-ready notes: {notes_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
