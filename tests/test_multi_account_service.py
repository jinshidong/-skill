import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from multi_account_service import create_app  # noqa: E402
from wechat_draft_api import DraftValidationError, WeChatAPIError, WeChatDraftClient  # noqa: E402


class SequencePublisher:
    def __init__(self, outcomes: List[Any]) -> None:
        self.outcomes = list(outcomes)
        self.calls: List[Dict[str, Any]] = []

    def __call__(self, md_file: str, **kwargs: Any) -> Dict[str, Any]:
        self.calls.append(
            {
                "md_file": md_file,
                "kwargs": kwargs,
            }
        )
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class MultiAccountServiceTests(unittest.TestCase):
    def _create_client(self, publisher: SequencePublisher) -> Any:
        self.tempdir = tempfile.TemporaryDirectory()
        db_path = Path(self.tempdir.name) / "multiuser.sqlite"
        app = create_app(database_path=db_path, publisher=publisher)
        app.testing = True
        self.app = app
        return app.test_client()

    def tearDown(self) -> None:
        tempdir = getattr(self, "tempdir", None)
        if tempdir is not None:
            tempdir.cleanup()

    def _create_account(self, client: Any, **overrides: Any) -> Dict[str, Any]:
        payload = {
            "alias": "tech_daily",
            "wechat_appid": "APPID_TECH",
            "wechat_app_secret": "SECRET_TECH",
            "public_name": "技术日报",
            "description": "默认技术号",
            "enabled": True,
        }
        payload.update(overrides)
        response = client.post("/api/accounts", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertTrue(data["ok"])
        return data["account"]

    def _write_article_fixture(self, root: Path) -> Path:
        article_path = root / "article.md"
        article_path.write_text(
            "\n".join(
                [
                    "---",
                    'title: "原始稿标题"',
                    "---",
                    "",
                    "# 原始稿标题",
                    "",
                    "正文。",
                ]
            ),
            encoding="utf-8",
        )
        return article_path

    def test_account_crud_and_alias_uniqueness(self) -> None:
        client = self._create_client(SequencePublisher([]))
        account = self._create_account(client)

        accounts_response = client.get("/api/accounts")
        self.assertEqual(accounts_response.status_code, 200)
        accounts_payload = accounts_response.get_json()
        self.assertEqual(len(accounts_payload["accounts"]), 1)
        self.assertTrue(accounts_payload["accounts"][0]["enabled"])

        update_response = client.put(
            f"/api/accounts/{account['id']}",
            json={
                "alias": "tech_daily",
                "wechat_appid": "APPID_UPDATED",
                "wechat_app_secret": "SECRET_UPDATED",
                "public_name": "技术日报新版",
                "description": "已经更新",
                "enabled": False,
            },
        )
        self.assertEqual(update_response.status_code, 200)
        updated = update_response.get_json()["account"]
        self.assertFalse(updated["enabled"])
        self.assertEqual(updated["wechat_appid"], "APPID_UPDATED")

        duplicate_response = client.post(
            "/api/accounts",
            json={
                "alias": "tech_daily",
                "wechat_appid": "ANOTHER_APPID",
                "wechat_app_secret": "ANOTHER_SECRET",
                "public_name": "重复账号",
                "description": "",
                "enabled": True,
            },
        )
        self.assertEqual(duplicate_response.status_code, 409)
        self.assertIn("alias 已存在", duplicate_response.get_json()["error"])

        delete_response = client.delete(f"/api/accounts/{account['id']}")
        self.assertEqual(delete_response.status_code, 200)

        after_delete = client.get("/api/accounts").get_json()
        self.assertEqual(after_delete["accounts"], [])

        accounts_page = client.get("/accounts")
        self.assertEqual(accounts_page.status_code, 200)
        self.assertIn("风险警告".encode("utf-8"), accounts_page.data)

    def test_create_draft_uses_account_credentials_and_camera_ready_article(self) -> None:
        publisher = SequencePublisher(
            [
                {
                    "ok": True,
                    "title": "终稿标题",
                    "media_id": "MEDIA_123",
                    "thumb_media_id": "THUMB_123",
                }
            ]
        )
        client = self._create_client(publisher)
        self._create_account(client)

        workspace = Path(self.tempdir.name)
        article_path = self._write_article_fixture(workspace)
        camera_ready_path = workspace / "article.camera-ready.md"
        camera_ready_path.write_text(
            "\n".join(
                [
                    "---",
                    'title: "终稿标题"',
                    "---",
                    "",
                    "# 终稿标题",
                    "",
                    "终稿正文。",
                ]
            ),
            encoding="utf-8",
        )

        response = client.post(
            "/api/drafts",
            json={
                "account_alias": "tech_daily",
                "article_path": str(article_path),
                "source": "openclaw.telegram",
                "request_text": "生成公众号稿：公众号=tech_daily 主题=测试",
                "style": "tech",
                "author": "机器人",
                "digest": "一段摘要",
                "source_url": "https://example.com/article",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["title"], "终稿标题")
        self.assertEqual(payload["media_id"], "MEDIA_123")

        self.assertEqual(len(publisher.calls), 1)
        call = publisher.calls[0]
        self.assertEqual(call["md_file"], str(camera_ready_path.resolve()))
        self.assertEqual(call["kwargs"]["style"], "tech")
        self.assertEqual(call["kwargs"]["author"], "机器人")
        self.assertEqual(call["kwargs"]["digest"], "一段摘要")
        self.assertEqual(call["kwargs"]["content_source_url"], "https://example.com/article")
        self.assertIsInstance(call["kwargs"]["client"], WeChatDraftClient)
        self.assertEqual(call["kwargs"]["client"].appid, "APPID_TECH")
        self.assertEqual(call["kwargs"]["client"].secret, "SECRET_TECH")

        jobs = self.app.config["MD2WECHAT_MULTIUSER_STORE"].list_jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["status"], "success")
        self.assertEqual(jobs[0]["title"], "终稿标题")

    def test_missing_or_unknown_alias_returns_available_aliases(self) -> None:
        client = self._create_client(SequencePublisher([]))
        self._create_account(client, alias="tech_daily")
        self._create_account(
            client,
            alias="disabled_daily",
            wechat_appid="APPID_DISABLED",
            wechat_app_secret="SECRET_DISABLED",
            enabled=False,
        )

        missing_alias = client.post(
            "/api/drafts",
            json={
                "article_path": "/tmp/article.md",
                "source": "openclaw.telegram",
            },
        )
        self.assertEqual(missing_alias.status_code, 400)
        self.assertEqual(missing_alias.get_json()["available_aliases"], ["tech_daily"])

        unknown_alias = client.post(
            "/api/drafts",
            json={
                "account_alias": "unknown_alias",
                "article_path": "/tmp/article.md",
                "source": "openclaw.telegram",
            },
        )
        self.assertEqual(unknown_alias.status_code, 404)
        self.assertEqual(unknown_alias.get_json()["available_aliases"], ["tech_daily"])

    def test_disabled_account_cannot_deliver(self) -> None:
        client = self._create_client(SequencePublisher([]))
        self._create_account(
            client,
            alias="disabled_daily",
            wechat_appid="APPID_DISABLED",
            wechat_app_secret="SECRET_DISABLED",
            enabled=False,
        )

        response = client.post(
            "/api/drafts",
            json={
                "account_alias": "disabled_daily",
                "article_path": "/tmp/article.md",
                "source": "openclaw.telegram",
            },
        )
        self.assertEqual(response.status_code, 409)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "rejected")

        jobs = self.app.config["MD2WECHAT_MULTIUSER_STORE"].list_jobs()
        self.assertEqual(jobs, [])

    def test_validation_failure_writes_failed_history(self) -> None:
        publisher = SequencePublisher(
            [
                DraftValidationError("Markdown 文件不存在: /tmp/missing.md"),
            ]
        )
        client = self._create_client(publisher)
        self._create_account(client)

        response = client.post(
            "/api/drafts",
            json={
                "account_alias": "tech_daily",
                "article_path": "/tmp/missing.md",
                "source": "openclaw.telegram",
            },
        )
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertIsNotNone(payload["job_id"])
        self.assertIn("Markdown 文件不存在", payload["error"])

        jobs = self.app.config["MD2WECHAT_MULTIUSER_STORE"].list_jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["status"], "failed")
        self.assertIn("Markdown 文件不存在", jobs[0]["error_message"])

    def test_retry_creates_new_job_and_reuses_request_overrides(self) -> None:
        publisher = SequencePublisher(
            [
                WeChatAPIError("微信接口调用失败: errcode=500, errmsg=boom"),
                {
                    "ok": True,
                    "title": "重试成功标题",
                    "media_id": "MEDIA_RETRY",
                    "thumb_media_id": "THUMB_RETRY",
                },
            ]
        )
        client = self._create_client(publisher)
        self._create_account(client)
        article_path = self._write_article_fixture(Path(self.tempdir.name))

        first_response = client.post(
            "/api/drafts",
            json={
                "account_alias": "tech_daily",
                "article_path": str(article_path),
                "source": "openclaw.telegram",
                "request_text": "生成公众号稿：公众号=tech_daily 主题=重试测试",
                "style": "tech",
                "author": "重试作者",
                "digest": "重试摘要",
                "source_url": "https://example.com/retry",
            },
        )
        self.assertEqual(first_response.status_code, 502)
        first_job_id = first_response.get_json()["job_id"]

        retry_response = client.post(f"/jobs/{first_job_id}/retry", follow_redirects=True)
        self.assertEqual(retry_response.status_code, 200)
        self.assertIn("重试成功".encode("utf-8"), retry_response.data)

        self.assertEqual(len(publisher.calls), 2)
        retry_call = publisher.calls[1]
        self.assertEqual(retry_call["kwargs"]["style"], "tech")
        self.assertEqual(retry_call["kwargs"]["author"], "重试作者")
        self.assertEqual(retry_call["kwargs"]["digest"], "重试摘要")
        self.assertEqual(retry_call["kwargs"]["content_source_url"], "https://example.com/retry")

        jobs = self.app.config["MD2WECHAT_MULTIUSER_STORE"].list_jobs()
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0]["status"], "success")
        self.assertEqual(jobs[0]["title"], "重试成功标题")
        self.assertEqual(jobs[1]["status"], "failed")

        jobs_page = client.get("/jobs")
        self.assertEqual(jobs_page.status_code, 200)
        self.assertIn("风险警告".encode("utf-8"), jobs_page.data)
        self.assertIn("重试成功标题".encode("utf-8"), jobs_page.data)


if __name__ == "__main__":
    unittest.main()
