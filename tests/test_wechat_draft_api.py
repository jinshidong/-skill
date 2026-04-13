import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest import mock

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import md2wechat_config  # noqa: E402
from wechat_draft_api import (  # noqa: E402
    DraftValidationError,
    WeChatAPIError,
    WeChatDraftClient,
    create_draft_from_markdown,
)


class FakeDraftClient:
    def __init__(self) -> None:
        self.uploaded_article_images: List[Dict[str, Any]] = []
        self.uploaded_cover: Optional[Dict[str, Any]] = None
        self.created_article: Optional[Dict[str, Any]] = None

    def upload_article_image(self, image_bytes: bytes, filename: str, mime_type: str) -> str:
        self.uploaded_article_images.append(
            {
                "bytes": image_bytes,
                "filename": filename,
                "mime_type": mime_type,
            }
        )
        suffix = Path(filename).suffix or ".jpg"
        return f"https://mmbiz.qpic.cn/mock/article{len(self.uploaded_article_images)}{suffix}"

    def upload_cover_image(self, image_bytes: bytes, filename: str, mime_type: str) -> str:
        self.uploaded_cover = {
            "bytes": image_bytes,
            "filename": filename,
            "mime_type": mime_type,
        }
        return "THUMB_MEDIA_ID"

    def create_draft(self, article_payload: Dict[str, Any]) -> str:
        self.created_article = article_payload
        return "DRAFT_MEDIA_ID"


class FakeRetryDraftClient(FakeDraftClient):
    def __init__(self) -> None:
        super().__init__()
        self.create_calls = 0

    def create_draft(self, article_payload: Dict[str, Any]) -> str:
        self.create_calls += 1
        if self.create_calls == 1:
            raise WeChatAPIError("微信接口调用失败: errcode=45004, errmsg=description size out of limit")
        self.created_article = article_payload
        return "DRAFT_MEDIA_ID"


class FakeResponse:
    def __init__(self, payload: Dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self) -> Dict[str, Any]:
        return self._payload


class FakeSession:
    def __init__(self) -> None:
        self.requests: List[Dict[str, Any]] = []
        self.responses = [
            FakeResponse({"access_token": "ACCESS_TOKEN", "expires_in": 7200}),
            FakeResponse({"url": "https://mmbiz.qpic.cn/mock/uploaded_article.jpg"}),
            FakeResponse({"media_id": "THUMB_MEDIA_ID"}),
            FakeResponse({"media_id": "DRAFT_MEDIA_ID"}),
        ]

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.requests.append({"method": method, "url": url, "kwargs": kwargs})
        return self.responses.pop(0)


class WeChatDraftApiTests(unittest.TestCase):
    def _create_fixture_files(
        self,
        root: Path,
        *,
        include_cover_in_frontmatter: bool = True,
        include_author_in_frontmatter: bool = True,
    ) -> Path:
        cover_path = root / "cover.png"
        body_path = root / "body.png"

        Image.new("RGB", (640, 360), (255, 128, 0)).save(cover_path)
        Image.new("RGBA", (48, 48), (0, 128, 255, 255)).save(body_path)

        front_matter = [
            "---",
            'title: "测试文章"',
            "date: 2026-04-02",
            'excerpt: "这是摘要"',
            'permalink: "https://example.com/source"',
        ]
        if include_author_in_frontmatter:
            front_matter.append('author: "作者A"')
        if include_cover_in_frontmatter:
            front_matter.append('cover: "./cover.png"')
        front_matter.extend(
            [
                "---",
                "",
                "正文第一段。",
                "",
                "![示意图](./body.png)",
            ]
        )

        md_path = root / "article.md"
        md_path.write_text("\n".join(front_matter), encoding="utf-8")
        return md_path

    def test_dry_run_rewrites_images_and_builds_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = self._create_fixture_files(Path(tmpdir))
            result = create_draft_from_markdown(str(md_path), style="academic_gray", dry_run=True)

            self.assertTrue(result["ok"])
            self.assertTrue(result["dry_run"])
            article_payload = result["payload"]["articles"][0]
            self.assertEqual(article_payload["title"], "测试文章")
            self.assertEqual(article_payload["author"], "作者A")
            self.assertEqual(article_payload["digest"], "这是摘要")
            self.assertEqual(article_payload["content_source_url"], "https://example.com/source")
            self.assertEqual(article_payload["thumb_media_id"], "DRY_RUN_THUMB_MEDIA_ID")
            self.assertNotIn("data:image", article_payload["content"])
            self.assertIn("https://mmbiz.qpic.cn/mock/md2wechat/draft_image_1", article_payload["content"])
            self.assertNotIn("<section", article_payload["content"])

    def test_footer_and_closing_sections_stay_at_article_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = self._create_fixture_files(Path(tmpdir))
            result = create_draft_from_markdown(str(md_path), dry_run=True)

            content = result["payload"]["articles"][0]["content"]
            footer_index = content.find("来源：")
            focus_index = content.find("互动提示")
            reader_index = content.find("读者征稿")
            reader_title_index = content.find("读者来稿")

            self.assertGreaterEqual(footer_index, 0)
            self.assertGreater(focus_index, footer_index)
            self.assertGreater(reader_index, focus_index)
            self.assertGreater(reader_title_index, reader_index)
            self.assertNotIn("<section", content)
            self.assertEqual(content.rfind("来源："), footer_index)
            self.assertEqual(content.rfind("互动提示"), focus_index)
            self.assertEqual(content.rfind("读者征稿"), reader_index)
            self.assertEqual(content.rfind("读者来稿"), reader_title_index)

    def test_create_draft_with_mock_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = self._create_fixture_files(Path(tmpdir))
            client = FakeDraftClient()
            result = create_draft_from_markdown(str(md_path), style="academic_gray", client=client)

            self.assertTrue(result["ok"])
            self.assertEqual(result["thumb_media_id"], "THUMB_MEDIA_ID")
            self.assertEqual(result["media_id"], "DRAFT_MEDIA_ID")
            self.assertEqual(len(client.uploaded_article_images), 1)
            self.assertIsNotNone(client.uploaded_cover)
            self.assertIsNotNone(client.created_article)
            self.assertEqual(client.created_article["title"], "测试文章")
            self.assertEqual(client.created_article["content_source_url"], "https://example.com/source")
            self.assertNotIn("data:image", client.created_article["content"])

    def test_client_calls_expected_wechat_endpoints(self) -> None:
        session = FakeSession()
        client = WeChatDraftClient("APPID", "SECRET", session=session)

        token = client.get_access_token()
        article_url = client.upload_article_image(b"article", "article.jpg", "image/jpeg")
        thumb_media_id = client.upload_cover_image(b"cover", "cover.jpg", "image/jpeg")
        draft_media_id = client.create_draft(
            {
                "title": "标题",
                "content": "<section>content</section>",
                "thumb_media_id": "THUMB_MEDIA_ID",
            }
        )

        self.assertEqual(token, "ACCESS_TOKEN")
        self.assertEqual(article_url, "https://mmbiz.qpic.cn/mock/uploaded_article.jpg")
        self.assertEqual(thumb_media_id, "THUMB_MEDIA_ID")
        self.assertEqual(draft_media_id, "DRAFT_MEDIA_ID")
        self.assertEqual(len(session.requests), 4)
        self.assertTrue(session.requests[0]["url"].endswith("/stable_token"))
        self.assertTrue(session.requests[1]["url"].endswith("/media/uploadimg"))
        self.assertTrue(session.requests[2]["url"].endswith("/material/add_material"))
        self.assertTrue(session.requests[3]["url"].endswith("/draft/add"))

    def test_retry_with_shorter_digest_on_description_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = self._create_fixture_files(Path(tmpdir))
            client = FakeRetryDraftClient()
            result = create_draft_from_markdown(
                str(md_path),
                style="academic_gray",
                digest="这是一段明显长于保守摘要策略的测试摘要，用来验证重试时会自动缩短摘要内容。",
                client=client,
            )

            self.assertTrue(result["ok"])
            self.assertEqual(client.create_calls, 2)
            self.assertIsNotNone(client.created_article)
            self.assertLessEqual(len(client.created_article["digest"]), 54)

    def test_author_falls_back_to_default_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = self._create_fixture_files(
                Path(tmpdir),
                include_author_in_frontmatter=False,
            )
            result = create_draft_from_markdown(str(md_path), style="academic_gray", dry_run=True)

            article_payload = result["payload"]["articles"][0]
            self.assertEqual(article_payload["author"], "路人甲")

    def test_cover_can_fall_back_to_article_defaults_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            md_path = self._create_fixture_files(tmp_path, include_cover_in_frontmatter=False)
            config_dir = tmp_path / "config"
            config_dir.mkdir()
            Image.new("RGB", (640, 360), (32, 64, 128)).save(config_dir / "default-cover.png")
            config_path = config_dir / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "article_defaults:",
                        '  cover: "./default-cover.png"',
                        '  author: "默认作者"',
                    ]
                ),
                encoding="utf-8",
            )

            with mock.patch.object(md2wechat_config, "DEFAULT_CONFIG_PATH", config_path):
                result = create_draft_from_markdown(str(md_path), style="academic_gray", dry_run=True)

            self.assertEqual(result["cover_path"], str((config_dir / "default-cover.png").resolve()))
            self.assertEqual(result["author"], "作者A")

    def test_default_style_follows_config_when_style_not_provided(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            md_path = self._create_fixture_files(tmp_path)
            config_path = tmp_path / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "camera_ready:",
                        '  style: "tech"',
                    ]
                ),
                encoding="utf-8",
            )

            with mock.patch.object(md2wechat_config, "DEFAULT_CONFIG_PATH", config_path):
                result = create_draft_from_markdown(str(md_path), dry_run=True)

            article_payload = result["payload"]["articles"][0]
            self.assertIn("background-color:#E3F2FD", article_payload["content"])
            self.assertIn("color:#0D47A1", article_payload["content"])

    def test_documented_viral_style_alias_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = self._create_fixture_files(Path(tmpdir))
            result = create_draft_from_markdown(
                str(md_path),
                style="viral-writer-wechat",
                dry_run=True,
            )

            self.assertTrue(result["ok"])

    def test_invalid_article_default_cover_raises_validation_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            md_path = self._create_fixture_files(tmp_path, include_cover_in_frontmatter=False)
            config_path = tmp_path / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "article_defaults:",
                        '  cover: "./missing-cover.png"',
                    ]
                ),
                encoding="utf-8",
            )

            with mock.patch.object(md2wechat_config, "DEFAULT_CONFIG_PATH", config_path):
                with self.assertRaises(DraftValidationError):
                    create_draft_from_markdown(str(md_path), style="academic_gray", dry_run=True)

    def test_client_can_read_credentials_from_config_when_env_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "wechat:",
                        '  appid: "CONFIG_APPID"',
                        '  secret: "CONFIG_SECRET"',
                    ]
                ),
                encoding="utf-8",
            )

            with mock.patch.object(md2wechat_config, "DEFAULT_CONFIG_PATH", config_path):
                with mock.patch.dict(os.environ, {"WECHAT_APPID": "", "WECHAT_SECRET": ""}, clear=False):
                    client = WeChatDraftClient.from_env()

            self.assertEqual(client.appid, "CONFIG_APPID")
            self.assertEqual(client.secret, "CONFIG_SECRET")

    def test_metadata_precedence_is_cli_then_front_matter_then_config_then_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            md_path = self._create_fixture_files(tmp_path)
            cli_cover_path = tmp_path / "cli-cover.png"
            Image.new("RGB", (640, 360), (255, 255, 0)).save(cli_cover_path)

            config_path = tmp_path / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "article_defaults:",
                        '  author: "配置作者"',
                        '  digest: "配置摘要"',
                        '  cover: "./config-cover.png"',
                        '  source_url: "https://example.com/config-source"',
                    ]
                ),
                encoding="utf-8",
            )
            Image.new("RGB", (640, 360), (128, 0, 255)).save(tmp_path / "config-cover.png")

            with mock.patch.object(md2wechat_config, "DEFAULT_CONFIG_PATH", config_path):
                result = create_draft_from_markdown(
                    str(md_path),
                    style="academic_gray",
                    author="CLI作者",
                    digest="CLI摘要",
                    content_source_url="https://example.com/cli-source",
                    cover_image_path=str(cli_cover_path),
                    dry_run=True,
                )

            article_payload = result["payload"]["articles"][0]
            self.assertEqual(article_payload["author"], "CLI作者")
            self.assertEqual(article_payload["digest"], "CLI摘要")
            self.assertEqual(article_payload["content_source_url"], "https://example.com/cli-source")
            self.assertEqual(result["cover_path"], str(cli_cover_path.resolve()))


if __name__ == "__main__":
    unittest.main()
