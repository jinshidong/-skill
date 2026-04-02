#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号草稿创建命令行工具

将 Markdown 文件转换为微信公众号兼容的 HTML，并通过微信官方草稿箱 API
自动创建单篇图文草稿。
"""

import argparse
import json
import sys
from pathlib import Path

# 添加 src 目录到路径
src_path = str(Path(__file__).parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from md2wechat_config import resolve_publish_article_path  # type: ignore
from md2wechat import STYLES  # type: ignore
from wechat_draft_api import DraftValidationError, WeChatAPIError, create_draft_from_markdown  # type: ignore


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description="创建微信公众号单篇图文草稿",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 创建草稿（优先读 WECHAT_APPID / WECHAT_SECRET，缺失时回退到 ~/.config/md2wechat/config.yaml）
  python publish_wechat.py article.md --cover cover.jpg

  # 指定风格和摘要
  python publish_wechat.py article.md --cover cover.jpg --style festival --digest "文章摘要"

  # 只做本地预检，不调用微信接口
  python publish_wechat.py article.md --cover cover.jpg --dry-run

  # 如果 article.camera-ready.md 存在，将优先使用终稿；若未传 --cover 且 front matter 也没写 cover，将回退到 examples/images/frontpage.png
  python publish_wechat.py article.md --dry-run
        """,
    )


def main() -> int:
    parser = build_parser()
    parser.add_argument("md_file", help="Markdown 文件路径")
    parser.add_argument(
        "--style",
        "-s",
        default="academic_gray",
        choices=list(STYLES.keys()),
        help="HTML 风格（默认: academic_gray）",
    )
    parser.add_argument(
        "--cover",
        help="封面图片路径（本地文件，优先级高于 front matter.cover；未提供时回退到 examples/images/frontpage.png）",
    )
    parser.add_argument("--title", help="覆盖文章标题")
    parser.add_argument("--author", help="覆盖文章作者")
    parser.add_argument("--digest", help="覆盖文章摘要")
    parser.add_argument("--source", help="覆盖文章底部来源信息")
    parser.add_argument("--source-url", help="覆盖阅读原文链接（content_source_url）")
    parser.add_argument("--dry-run", action="store_true", help="仅做本地预检，不调用微信接口")
    args = parser.parse_args()

    try:
        md_path = resolve_publish_article_path(args.md_file)
    except ValueError as exc:
        print(f"错误: {exc}")
        return 1
    if not md_path.exists():
        print(f"错误: Markdown 文件不存在: {md_path}")
        return 1

    try:
        result = create_draft_from_markdown(
            str(md_path),
            style=args.style,
            cover_image_path=args.cover,
            title=args.title,
            author=args.author,
            digest=args.digest,
            source=args.source,
            content_source_url=args.source_url,
            dry_run=args.dry_run,
        )
    except DraftValidationError as exc:
        print(f"❌ 本地预检失败: {exc}")
        return 1
    except WeChatAPIError as exc:
        print(f"❌ 微信接口调用失败: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - CLI 兜底
        print(f"❌ 未知错误: {exc}")
        return 1

    if result.get("dry_run"):
        print("✅ 本地预检通过")
        print(f"   标题: {result.get('title', '')}")
        print(f"   作者: {result.get('author', '')}")
        print(f"   摘要: {result.get('digest', '')}")
        print(f"   阅读原文: {result.get('content_source_url', '')}")
        print(f"   封面: {result.get('cover_path', '')}")
        print(f"   正文图片数量: {result.get('article_image_count', 0)}")
        print(f"   正文长度: {result.get('content_length', 0)} 字符")
        print("\nDraft Payload:")
        print(json.dumps(result.get("payload", {}), ensure_ascii=False, indent=2))
        return 0

    print("✅ 草稿创建成功")
    print(f"   标题: {result.get('title', '')}")
    print(f"   封面素材 ID: {result.get('thumb_media_id', '')}")
    print(f"   草稿 Media ID: {result.get('media_id', '')}")
    print(f"   正文图片数量: {result.get('article_image_count', 0)}")
    print(f"   正文长度: {result.get('content_length', 0)} 字符")
    return 0


if __name__ == "__main__":
    sys.exit(main())
