import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from md2wechat import WeChatHTMLConverter  # noqa: E402


class WeChatHTMLRenderTests(unittest.TestCase):
    def test_render_article_uses_block_wrappers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            image_path = tmp_path / "body.png"
            Image.new("RGB", (32, 32), (0, 128, 255)).save(image_path)

            md_path = tmp_path / "article.md"
            md_path.write_text(
                "\n".join(
                    [
                        "---",
                        'title: "测试标题"',
                        "date: 2026-04-02",
                        "tags:",
                        "  - 测试",
                        "---",
                        "",
                        "正文内容。",
                        "",
                        "![示意图](./body.png)",
                    ]
                ),
                encoding="utf-8",
            )

            converter = WeChatHTMLConverter(style="academic_gray", base_dir=str(tmp_path))
            rendered = converter.render_article(str(md_path))

            self.assertEqual(rendered.title, "测试标题")
            self.assertIn("<section", rendered.html)
            self.assertIn('<section style="border:1px solid', rendered.html)
            self.assertNotIn('<p style="border:1px solid', rendered.html)
            self.assertIn("data:image", rendered.html)


if __name__ == "__main__":
    unittest.main()
