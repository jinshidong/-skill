import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

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
    def _create_fixture_files(self, root: Path, *, include_cover_in_frontmatter: bool = True) -> Path:
        cover_path = root / "cover.png"
        body_path = root / "body.png"

        Image.new("RGB", (640, 360), (255, 128, 0)).save(cover_path)
        Image.new("RGBA", (48, 48), (0, 128, 255, 255)).save(body_path)

        front_matter = [
            "---",
            'title: "测试文章"',
            "date: 2026-04-02",
            'author: "作者A"',
            'excerpt: "这是摘要"',
            'permalink: "https://example.com/source"',
        ]
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

    def test_missing_cover_raises_validation_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = self._create_fixture_files(Path(tmpdir), include_cover_in_frontmatter=False)
            with self.assertRaises(DraftValidationError):
                create_draft_from_markdown(str(md_path), style="academic_gray", dry_run=True)


if __name__ == "__main__":
    unittest.main()
