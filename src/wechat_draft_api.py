#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号草稿箱 API 发布模块

将 Markdown 渲染后的 HTML 转换为微信草稿箱可接受的 payload，
并通过官方接口上传正文图片、封面图和创建草稿。
"""

import base64
import io
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageOps, UnidentifiedImageError

try:
    from md2wechat_config import (
        DEFAULT_AUTHOR_NAME,
        Md2WeChatConfig,
        get_article_defaults,
        load_md2wechat_config,
        resolve_path_from_value,
        resolve_publish_article_path,
        resolve_value,
        resolve_wechat_credentials,
    )
    from md2wechat import MarkdownParser, RenderedArticle, WeChatHTMLConverter
except ImportError:
    from .md2wechat_config import (
        DEFAULT_AUTHOR_NAME,
        Md2WeChatConfig,
        get_article_defaults,
        load_md2wechat_config,
        resolve_path_from_value,
        resolve_publish_article_path,
        resolve_value,
        resolve_wechat_credentials,
    )
    from .md2wechat import MarkdownParser, RenderedArticle, WeChatHTMLConverter


WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"
DEFAULT_TIMEOUT = 30
ARTICLE_IMAGE_MAX_BYTES = 1024 * 1024
THUMB_IMAGE_MAX_BYTES = 64 * 1024
MAX_CONTENT_BYTES = 1024 * 1024
MAX_CONTENT_CHARS = 20000
SAFE_DIGEST_CHARS = 54
# Repo-relative fallback cover so the default works on other machines too.
DEFAULT_COVER_RELATIVE_PATH = Path("examples/images/frontpage.png")


class DraftValidationError(ValueError):
    """草稿创建前的本地校验错误"""


class WeChatAPIError(RuntimeError):
    """微信官方接口错误"""


@dataclass
class DraftMetadata:
    """草稿元信息"""

    title: str
    author: str = ""
    digest: str = ""
    content_source_url: str = ""
    cover_path: str = ""
    source: str = "gnss.ac.cn"


@dataclass
class PreparedDraft:
    """本地准备完成、可直接上传的草稿"""

    metadata: DraftMetadata
    rendered_article: RenderedArticle
    content_html: str
    article_image_count: int
    cover_bytes: bytes
    cover_filename: str
    cover_mime_type: str


class WeChatDraftClient:
    """微信草稿箱官方 API 客户端"""

    def __init__(
        self,
        appid: str,
        secret: str,
        session: Optional[requests.Session] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.appid = appid
        self.secret = secret
        self.session = session or requests.Session()
        self.timeout = timeout
        self._access_token: Optional[str] = None
        self._access_token_expire_at = 0.0

    @classmethod
    def from_env(
        cls,
        session: Optional[requests.Session] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> "WeChatDraftClient":
        credentials = resolve_wechat_credentials(load_md2wechat_config())
        if not credentials.appid or not credentials.secret:
            raise DraftValidationError(
                "缺少公众号凭证；请设置 WECHAT_APPID/WECHAT_SECRET，或在 ~/.config/md2wechat/config.yaml 中配置 wechat.appid / wechat.secret"
            )

        return cls(
            appid=credentials.appid,
            secret=credentials.secret,
            session=session,
            timeout=timeout,
        )

    def get_access_token(self) -> str:
        """获取稳定版 access_token"""
        now = time.time()
        if self._access_token and now < self._access_token_expire_at - 300:
            return self._access_token

        payload = {
            "grant_type": "client_credential",
            "appid": self.appid,
            "secret": self.secret,
            "force_refresh": False,
        }
        data = self._request_json("POST", "/stable_token", json_payload=payload, use_access_token=False)
        token = data.get("access_token", "")
        if not token:
            raise WeChatAPIError("获取 access_token 失败：响应中缺少 access_token")

        self._access_token = token
        self._access_token_expire_at = now + int(data.get("expires_in", 0))
        return token

    def upload_article_image(self, image_bytes: bytes, filename: str, mime_type: str) -> str:
        """上传正文图片，返回微信图片 URL"""
        data = self._request_json(
            "POST",
            "/media/uploadimg",
            params={"access_token": self.get_access_token()},
            files={"media": (filename, image_bytes, mime_type)},
        )
        url = data.get("url", "")
        if not url:
            raise WeChatAPIError("上传正文图片失败：响应中缺少 url")
        return url

    def upload_cover_image(self, image_bytes: bytes, filename: str, mime_type: str) -> str:
        """上传封面图，返回永久 thumb_media_id"""
        data = self._request_json(
            "POST",
            "/material/add_material",
            params={
                "access_token": self.get_access_token(),
                "type": "thumb",
            },
            files={"media": (filename, image_bytes, mime_type)},
        )
        media_id = data.get("media_id", "")
        if not media_id:
            raise WeChatAPIError("上传封面图失败：响应中缺少 media_id")
        return media_id

    def create_draft(self, article_payload: Dict[str, Any]) -> str:
        """创建草稿，返回草稿 media_id"""
        data = self._request_json(
            "POST",
            "/draft/add",
            params={"access_token": self.get_access_token()},
            json_payload={"articles": [article_payload]},
        )
        media_id = data.get("media_id", "")
        if not media_id:
            raise WeChatAPIError("创建草稿失败：响应中缺少 media_id")
        return media_id

    def _request_json(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_payload: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Tuple[str, bytes, str]]] = None,
        use_access_token: bool = True,
    ) -> Dict[str, Any]:
        url = endpoint if endpoint.startswith("http") else f"{WECHAT_API_BASE}{endpoint}"
        request_params = dict(params or {})
        if use_access_token and "access_token" not in request_params:
            request_params["access_token"] = self.get_access_token()

        response = self.session.request(
            method=method,
            url=url,
            params=request_params,
            data=json.dumps(json_payload, ensure_ascii=False).encode("utf-8") if json_payload is not None else None,
            files=files,
            headers={"Content-Type": "application/json; charset=utf-8"} if json_payload is not None else None,
            timeout=self.timeout,
        )
        response.raise_for_status()

        try:
            data = response.json()
        except ValueError as exc:
            raise WeChatAPIError(f"微信接口返回了非 JSON 响应: {response.text[:200]}") from exc

        errcode = data.get("errcode")
        if errcode not in (None, 0):
            errmsg = data.get("errmsg", "unknown error")
            raise WeChatAPIError(f"微信接口调用失败: errcode={errcode}, errmsg={errmsg}")

        return data


def prepare_draft_from_markdown(
    md_file: str,
    *,
    style: str = "academic_gray",
    cover_image_path: Optional[str] = None,
    title: Optional[str] = None,
    author: Optional[str] = None,
    digest: Optional[str] = None,
    source: Optional[str] = None,
    content_source_url: Optional[str] = None,
    image_uploader: Optional[Callable[[bytes, str, str], str]] = None,
) -> PreparedDraft:
    """准备草稿 payload 所需的本地内容"""
    try:
        md_path = resolve_publish_article_path(md_file)
    except ValueError as exc:
        raise DraftValidationError(str(exc)) from exc
    if not md_path.exists():
        raise DraftValidationError(f"Markdown 文件不存在: {md_path}")

    runtime_config = load_md2wechat_config()
    md_content = md_path.read_text(encoding="utf-8")
    parser = MarkdownParser(md_content)
    base_dir = md_path.parent
    article_defaults = get_article_defaults(runtime_config)
    resolved_source = resolve_value(
        source,
        parser.front_matter.get("source", ""),
        article_defaults.get("source", ""),
        "",
    )
    converter = WeChatHTMLConverter(style=style, base_dir=str(base_dir))
    rendered = converter.render_article(
        str(md_path),
        source=resolved_source.value or None,
    )

    metadata = _resolve_metadata(
        parser=parser,
        md_body=parser.body,
        base_dir=base_dir,
        rendered=rendered,
        runtime_config=runtime_config,
        cover_image_path=cover_image_path,
        title=title,
        author=author,
        digest=digest,
        content_source_url=content_source_url,
    )
    _validate_metadata(metadata)

    uploader = image_uploader or _build_dry_run_uploader()
    content_html, article_image_count = rewrite_html_images_for_wechat(
        rendered.html,
        base_dir=base_dir,
        image_uploader=uploader,
    )
    _validate_content_html(content_html)

    cover_bytes, cover_filename, cover_mime_type = prepare_cover_image(metadata.cover_path)

    return PreparedDraft(
        metadata=metadata,
        rendered_article=rendered,
        content_html=content_html,
        article_image_count=article_image_count,
        cover_bytes=cover_bytes,
        cover_filename=cover_filename,
        cover_mime_type=cover_mime_type,
    )


def create_draft_from_markdown(
    md_file: str,
    *,
    style: str = "academic_gray",
    cover_image_path: Optional[str] = None,
    title: Optional[str] = None,
    author: Optional[str] = None,
    digest: Optional[str] = None,
    source: Optional[str] = None,
    content_source_url: Optional[str] = None,
    dry_run: bool = False,
    client: Optional[WeChatDraftClient] = None,
) -> Dict[str, Any]:
    """从 Markdown 创建微信公众号草稿"""
    if dry_run:
        prepared = prepare_draft_from_markdown(
            md_file,
            style=style,
            cover_image_path=cover_image_path,
            title=title,
            author=author,
            digest=digest,
            source=source,
            content_source_url=content_source_url,
        )
        article_payload = build_draft_article_payload(
            prepared.metadata,
            prepared.content_html,
            thumb_media_id="DRY_RUN_THUMB_MEDIA_ID",
        )
        return {
            "ok": True,
            "dry_run": True,
            "message": "本地预检通过，未调用微信接口",
            "title": prepared.metadata.title,
            "author": prepared.metadata.author,
            "digest": prepared.metadata.digest,
            "content_source_url": prepared.metadata.content_source_url,
            "cover_path": prepared.metadata.cover_path,
            "article_image_count": prepared.article_image_count,
            "content_length": len(prepared.content_html),
            "payload": {"articles": [article_payload]},
        }

    draft_client = client or WeChatDraftClient.from_env()
    prepared = prepare_draft_from_markdown(
        md_file,
        style=style,
        cover_image_path=cover_image_path,
        title=title,
        author=author,
        digest=digest,
        source=source,
        content_source_url=content_source_url,
        image_uploader=draft_client.upload_article_image,
    )
    thumb_media_id = draft_client.upload_cover_image(
        prepared.cover_bytes,
        prepared.cover_filename,
        prepared.cover_mime_type,
    )
    article_payload = build_draft_article_payload(
        prepared.metadata,
        prepared.content_html,
        thumb_media_id=thumb_media_id,
    )
    try:
        media_id = draft_client.create_draft(article_payload)
    except WeChatAPIError as exc:
        if _should_retry_with_shorter_digest(exc, article_payload):
            fallback_digest = _make_safe_digest(prepared.metadata.digest, prepared.content_html)
            retry_payload = dict(article_payload)
            if fallback_digest:
                retry_payload["digest"] = fallback_digest
            else:
                retry_payload.pop("digest", None)
            media_id = draft_client.create_draft(retry_payload)
            article_payload = retry_payload
            prepared.metadata.digest = fallback_digest
        else:
            raise
    return {
        "ok": True,
        "dry_run": False,
        "message": "草稿创建成功",
        "title": prepared.metadata.title,
        "author": prepared.metadata.author,
        "digest": prepared.metadata.digest,
        "content_source_url": prepared.metadata.content_source_url,
        "cover_path": prepared.metadata.cover_path,
        "article_image_count": prepared.article_image_count,
        "content_length": len(prepared.content_html),
        "thumb_media_id": thumb_media_id,
        "media_id": media_id,
    }


def build_draft_article_payload(
    metadata: DraftMetadata,
    content_html: str,
    *,
    thumb_media_id: str,
) -> Dict[str, Any]:
    """构建微信 draft/add 所需的文章 payload"""
    article: Dict[str, Any] = {
        "article_type": "news",
        "title": metadata.title,
        "content": content_html,
        "thumb_media_id": thumb_media_id,
    }
    if metadata.author:
        article["author"] = metadata.author
    if metadata.digest:
        article["digest"] = metadata.digest
    if metadata.content_source_url:
        article["content_source_url"] = metadata.content_source_url
    return article


def rewrite_html_images_for_wechat(
    html: str,
    *,
    base_dir: Path,
    image_uploader: Callable[[bytes, str, str], str],
) -> Tuple[str, int]:
    """将 HTML 中的图片改写为微信 uploadimg 返回的 URL"""
    soup = BeautifulSoup(html, "html.parser")
    image_count = 0

    for image_count, img in enumerate(soup.find_all("img"), start=1):
        src = (img.get("src") or "").strip()
        if not src:
            raise DraftValidationError("HTML 中存在缺少 src 的图片标签")

        image_bytes, filename, mime_type = prepare_article_image(src, base_dir=base_dir, index=image_count)
        uploaded_url = image_uploader(image_bytes, filename, mime_type)
        img["src"] = uploaded_url
        if img.has_attr("srcset"):
            del img["srcset"]

    return soup.decode(formatter=None), image_count


def prepare_article_image(src: str, *, base_dir: Path, index: int) -> Tuple[bytes, str, str]:
    """读取并规范化正文图片"""
    raw_bytes, filename_hint, mime_type = _load_image_asset(src, base_dir=base_dir, default_stem=f"article_{index}")
    return _normalize_image_for_target(
        raw_bytes,
        filename_hint=filename_hint,
        mime_type=mime_type,
        max_bytes=ARTICLE_IMAGE_MAX_BYTES,
        prefer_png=True,
        force_jpeg=False,
    )


def prepare_cover_image(cover_path: str) -> Tuple[bytes, str, str]:
    """读取并规范化封面图"""
    cover_file = Path(cover_path).expanduser().resolve()
    if not cover_file.exists():
        raise DraftValidationError(f"封面图片不存在: {cover_file}")

    raw_bytes = cover_file.read_bytes()
    mime_type = _guess_mime_type(cover_file.name)
    return _normalize_image_for_target(
        raw_bytes,
        filename_hint=cover_file.name,
        mime_type=mime_type,
        max_bytes=THUMB_IMAGE_MAX_BYTES,
        prefer_png=False,
        force_jpeg=True,
    )


def _resolve_metadata(
    *,
    parser: MarkdownParser,
    md_body: str,
    base_dir: Path,
    rendered: RenderedArticle,
    runtime_config: Md2WeChatConfig,
    cover_image_path: Optional[str],
    title: Optional[str],
    author: Optional[str],
    digest: Optional[str],
    content_source_url: Optional[str],
) -> DraftMetadata:
    fm = parser.front_matter
    article_defaults = get_article_defaults(runtime_config)

    resolved_title = resolve_value(
        title,
        fm.get("title", ""),
        "",
        _extract_first_heading(md_body),
    ).value
    resolved_author = resolve_value(
        author,
        fm.get("author", ""),
        article_defaults.get("author", ""),
        DEFAULT_AUTHOR_NAME,
    ).value
    resolved_digest = resolve_value(
        digest,
        (
            str(fm.get("digest", "") or "")
            or str(fm.get("excerpt", "") or "")
            or str(fm.get("summary", "") or "")
            or str(fm.get("description", "") or "")
        ),
        article_defaults.get("digest", ""),
        "",
    ).value
    resolved_digest = _normalize_digest(resolved_digest)
    resolved_source_url = resolve_value(
        content_source_url,
        fm.get("permalink", ""),
        article_defaults.get("source_url", ""),
        "",
    ).value

    resolved_cover = resolve_value(
        cover_image_path,
        str(fm.get("cover", "") or fm.get("cover_image", "") or ""),
        article_defaults.get("cover", ""),
        "",
    )
    if resolved_cover.source == "fallback":
        cover_path = Path(__file__).resolve().parents[1] / DEFAULT_COVER_RELATIVE_PATH
        if not cover_path.exists():
            raise DraftValidationError(
                "缺少封面图，且默认封面不存在；请使用 --cover、front matter.cover，或补齐 examples/images/frontpage.png"
            )
    else:
        bases = [Path.cwd(), base_dir]
        if resolved_cover.source == "config":
            bases.insert(0, runtime_config.path.parent)
        cover_path = resolve_path_from_value(resolved_cover.value, bases=bases)
        if not cover_path.exists():
            raise DraftValidationError(f"封面图片不存在: {cover_path}")

    return DraftMetadata(
        title=resolved_title,
        author=resolved_author,
        digest=resolved_digest,
        content_source_url=resolved_source_url,
        cover_path=str(cover_path),
        source=rendered.source,
    )


def _validate_metadata(metadata: DraftMetadata) -> None:
    if not metadata.title:
        raise DraftValidationError("文章标题不能为空")
    if len(metadata.title) > 32:
        raise DraftValidationError("文章标题长度不能超过 32 个字符")
    if len(metadata.author) > 16:
        raise DraftValidationError("作者长度不能超过 16 个字符")
    if len(metadata.digest) > 128:
        raise DraftValidationError("摘要长度不能超过 128 个字符")
    if not metadata.cover_path:
        raise DraftValidationError("缺少封面图片路径")


def _validate_content_html(content_html: str) -> None:
    if "data:image" in content_html:
        raise DraftValidationError("正文 HTML 中仍然存在 data:image，说明图片未被成功替换为微信 URL")
    if len(content_html) > MAX_CONTENT_CHARS:
        raise DraftValidationError(f"正文 HTML 长度超过微信限制: {len(content_html)} > {MAX_CONTENT_CHARS}")
    content_bytes = content_html.encode("utf-8")
    if len(content_bytes) > MAX_CONTENT_BYTES:
        raise DraftValidationError(f"正文 HTML 字节数超过微信限制: {len(content_bytes)} > {MAX_CONTENT_BYTES}")


def _extract_first_heading(markdown_body: str) -> str:
    for line in markdown_body.splitlines():
        match = re.match(r"^\s{0,3}#\s+(.+?)\s*#*\s*$", line)
        if match:
            return match.group(1).strip()
    return ""


def _normalize_digest(value: str) -> str:
    """清理摘要中的多余空白，避免把格式字符带给微信接口"""
    return re.sub(r"\s+", " ", value).strip()


def _make_safe_digest(preferred_digest: str, content_html: str) -> str:
    """生成更保守的摘要，优先使用现有摘要，否则从正文提取前 54 字"""
    digest = _normalize_digest(preferred_digest)
    if digest:
        return digest[:SAFE_DIGEST_CHARS]

    soup = BeautifulSoup(content_html, "html.parser")
    text = _normalize_digest(soup.get_text(" ", strip=True))
    return text[:SAFE_DIGEST_CHARS]


def _should_retry_with_shorter_digest(exc: WeChatAPIError, article_payload: Dict[str, Any]) -> bool:
    message = str(exc).lower()
    return "description size out of limit" in message and bool(article_payload.get("digest"))


def _load_image_asset(src: str, *, base_dir: Path, default_stem: str) -> Tuple[bytes, str, str]:
    if src.startswith("data:"):
        return _decode_data_url(src, default_stem=default_stem)

    parsed = urlparse(src)
    if parsed.scheme in ("http", "https"):
        response = requests.get(src, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        filename = Path(parsed.path).name or f"{default_stem}.img"
        mime_type = response.headers.get("Content-Type", "").split(";")[0] or _guess_mime_type(filename)
        return response.content, filename, mime_type

    local_path = Path(src).expanduser()
    if not local_path.is_absolute():
        local_path = (base_dir / local_path).resolve()
    if not local_path.exists():
        raise DraftValidationError(f"图片文件不存在: {local_path}")

    return local_path.read_bytes(), local_path.name, _guess_mime_type(local_path.name)


def _decode_data_url(data_url: str, *, default_stem: str) -> Tuple[bytes, str, str]:
    match = re.match(r"^data:(?P<mime>[^;]+);base64,(?P<data>.+)$", data_url, re.DOTALL)
    if not match:
        raise DraftValidationError("不支持的 data URL 图片格式")

    mime_type = match.group("mime").strip().lower()
    extension = _extension_for_mime(mime_type)
    try:
        raw_bytes = base64.b64decode(match.group("data"), validate=True)
    except ValueError as exc:
        raise DraftValidationError("图片 data URL 不是合法的 base64 数据") from exc

    return raw_bytes, f"{default_stem}{extension}", mime_type


def _normalize_image_for_target(
    raw_bytes: bytes,
    *,
    filename_hint: str,
    mime_type: str,
    max_bytes: int,
    prefer_png: bool,
    force_jpeg: bool,
) -> Tuple[bytes, str, str]:
    try:
        image = Image.open(io.BytesIO(raw_bytes))
        image = ImageOps.exif_transpose(image)
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise DraftValidationError(f"无法识别图片文件: {filename_hint}") from exc

    if force_jpeg:
        encoded = _encode_jpeg_under_limit(image, max_bytes=max_bytes)
        return encoded, _replace_extension(filename_hint, ".jpg"), "image/jpeg"

    if prefer_png and _has_alpha(image):
        png_bytes = _encode_png_under_limit(image, max_bytes=max_bytes)
        if png_bytes is not None:
            return png_bytes, _replace_extension(filename_hint, ".png"), "image/png"

    jpeg_bytes = _encode_jpeg_under_limit(image, max_bytes=max_bytes)
    if jpeg_bytes is not None:
        return jpeg_bytes, _replace_extension(filename_hint, ".jpg"), "image/jpeg"

    png_bytes = _encode_png_under_limit(image, max_bytes=max_bytes)
    if png_bytes is not None:
        return png_bytes, _replace_extension(filename_hint, ".png"), "image/png"

    raise DraftValidationError(f"图片无法压缩到微信限制内: {filename_hint}")


def _encode_jpeg_under_limit(image: Image.Image, *, max_bytes: int) -> Optional[bytes]:
    working = _to_rgb(image)
    max_side = 1920 if max_bytes > THUMB_IMAGE_MAX_BYTES else 900
    working = _thumbnail_copy(working, max_side=max_side)

    for _ in range(8):
        for quality in (88, 82, 76, 70, 64, 58, 52, 46, 40, 34, 28, 24):
            output = io.BytesIO()
            working.save(output, format="JPEG", quality=quality, optimize=True)
            data = output.getvalue()
            if len(data) <= max_bytes:
                return data
        next_width = max(working.width * 85 // 100, 1)
        next_height = max(working.height * 85 // 100, 1)
        if next_width == working.width and next_height == working.height:
            break
        working = working.resize((next_width, next_height), Image.Resampling.LANCZOS)
    return None


def _encode_png_under_limit(image: Image.Image, *, max_bytes: int) -> Optional[bytes]:
    working = image.copy()
    max_side = 1920
    working = _thumbnail_copy(working, max_side=max_side)

    for _ in range(7):
        output = io.BytesIO()
        save_target = working
        if working.mode not in ("RGB", "RGBA", "L", "LA", "P"):
            save_target = working.convert("RGBA" if _has_alpha(working) else "RGB")
        save_target.save(output, format="PNG", optimize=True)
        data = output.getvalue()
        if len(data) <= max_bytes:
            return data
        next_width = max(working.width * 85 // 100, 1)
        next_height = max(working.height * 85 // 100, 1)
        if next_width == working.width and next_height == working.height:
            break
        working = working.resize((next_width, next_height), Image.Resampling.LANCZOS)
    return None


def _thumbnail_copy(image: Image.Image, *, max_side: int) -> Image.Image:
    working = image.copy()
    if max(working.size) <= max_side:
        return working
    working.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return working


def _to_rgb(image: Image.Image) -> Image.Image:
    if _has_alpha(image):
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image.convert("RGBA"), mask=image.convert("RGBA").getchannel("A"))
        return background
    if image.mode != "RGB":
        return image.convert("RGB")
    return image.copy()


def _has_alpha(image: Image.Image) -> bool:
    return image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)


def _replace_extension(filename: str, new_extension: str) -> str:
    return f"{Path(filename).stem}{new_extension}"


def _guess_mime_type(filename: str) -> str:
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }.get(Path(filename).suffix.lower(), "application/octet-stream")


def _extension_for_mime(mime_type: str) -> str:
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/bmp": ".bmp",
    }.get(mime_type, ".img")


def _build_dry_run_uploader() -> Callable[[bytes, str, str], str]:
    counter = {"value": 0}

    def _uploader(_image_bytes: bytes, filename: str, _mime_type: str) -> str:
        counter["value"] += 1
        suffix = Path(filename).suffix.lower() or ".jpg"
        return f"https://mmbiz.qpic.cn/mock/md2wechat/draft_image_{counter['value']}{suffix}"

    return _uploader
