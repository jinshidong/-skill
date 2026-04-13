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
            self.assertIn("关注支持", rendered.html)
            self.assertIn("读者来稿", rendered.html)
            self.assertGreater(rendered.html.index("关注支持"), rendered.html.index("正文内容"))
            self.assertGreater(rendered.html.index("读者来稿"), rendered.html.index("正文内容"))

    def test_render_article_falls_back_to_first_h1_for_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            md_path = tmp_path / "article.md"
            md_path.write_text(
                "\n".join(
                    [
                        "---",
                        "date: 2026-04-02",
                        "tags:",
                        "  - 测试",
                        "---",
                        "",
                        "# 正文标题",
                        "",
                        "正文内容。",
                    ]
                ),
                encoding="utf-8",
            )

            converter = WeChatHTMLConverter(style="academic_gray", base_dir=str(tmp_path))
            rendered = converter.render_article(str(md_path))

            self.assertEqual(rendered.title, "正文标题")
            self.assertIn("来源：gnss.ac.cn《正文标题》", rendered.html)

    def test_render_article_omits_empty_source_title_brackets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            md_path = tmp_path / "article.md"
            md_path.write_text(
                "\n".join(
                    [
                        "---",
                        "date: 2026-04-02",
                        "tags:",
                        "  - 测试",
                        "---",
                        "",
                        "正文内容。",
                    ]
                ),
                encoding="utf-8",
            )

            converter = WeChatHTMLConverter(style="academic_gray", base_dir=str(tmp_path))
            rendered = converter.render_article(str(md_path))

            self.assertEqual(rendered.title, "")
            self.assertIn("来源：gnss.ac.cn", rendered.html)
            self.assertNotIn("来源：gnss.ac.cn《》", rendered.html)

    def test_render_article_omits_empty_meta_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            md_path = tmp_path / "article.md"
            md_path.write_text(
                "\n".join(
                    [
                        "---",
                        "---",
                        "",
                        "正文内容。",
                    ]
                ),
                encoding="utf-8",
            )

            converter = WeChatHTMLConverter(style="academic_gray", base_dir=str(tmp_path))
            rendered = converter.render_article(str(md_path))

            self.assertNotIn("日期：", rendered.html)
            self.assertNotIn("标签：", rendered.html)
            self.assertIn("来源：gnss.ac.cn", rendered.html)

    def test_render_article_supports_colored_bold_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            md_path = tmp_path / "article.md"
            md_path.write_text(
                "\n".join(
                    [
                        "---",
                        'title: "彩色加粗测试"',
                        "date: 2026-04-08",
                        "---",
                        "",
                        "**红色重点**{red}",
                        "",
                        "**深蓝重点**{深蓝色}",
                        "",
                        "**普通加粗**",
                    ]
                ),
                encoding="utf-8",
            )

            converter = WeChatHTMLConverter(style="academic_gray", base_dir=str(tmp_path))
            rendered = converter.render_article(str(md_path))

            self.assertIn("红色重点", rendered.html)
            self.assertIn("深蓝重点", rendered.html)
            self.assertIn("普通加粗", rendered.html)
            self.assertIn("color:#c62828;", rendered.html)
            self.assertIn("color:#1d4ed8;", rendered.html)
            self.assertIn('<strong style="color:#1D4ED8;">普通加粗</strong>', rendered.html)


if __name__ == "__main__":
    unittest.main()
