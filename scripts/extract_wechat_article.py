#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号文章提取工具
支持下载文章、提取图片、OCR 识别、裁剪图片文字部分
"""

import os
import re
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from PIL import Image

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WeChatArticleExtractor:
    """微信公众号文章提取器"""
    
    def __init__(self, output_dir: str = "extracted_articles"):
        """
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir = self.output_dir / "images"
        self.images_dir.mkdir(exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://mp.weixin.qq.com/',
            'Cache-Control': 'max-age=0'
        })
        
        # 初始化 OCR（延迟加载）
        self._ocr_engine = None
    
    def _get_ocr_engine(self):
        """获取 OCR 引擎（延迟初始化）"""
        if self._ocr_engine is not None:
            return self._ocr_engine
        
        # 尝试使用 PaddleOCR（优先）
        try:
            from paddleocr import PaddleOCR
            # 使用新参数名（如果支持）
            try:
                self._ocr_engine = ('paddleocr', PaddleOCR(use_textline_orientation=True, lang='ch'))
            except TypeError:
                # 回退到旧参数名
                self._ocr_engine = ('paddleocr', PaddleOCR(use_angle_cls=True, lang='ch'))
            logger.info("使用 PaddleOCR 进行文字识别")
            return self._ocr_engine
        except ImportError:
            logger.debug("PaddleOCR 未安装")
        except Exception as e:
            logger.warning(f"PaddleOCR 初始化失败: {e}")
        
        # 尝试使用 pytesseract
        try:
            import pytesseract
            self._ocr_engine = ('tesseract', pytesseract)
            logger.info("使用 Tesseract 进行文字识别")
            return self._ocr_engine
        except ImportError:
            logger.debug("pytesseract 未安装")
        except Exception as e:
            logger.warning(f"Tesseract 初始化失败: {e}")
        
        # 没有可用的 OCR 引擎
        self._ocr_engine = (None, None)
        logger.warning("未找到可用的 OCR 引擎，将跳过文字识别")
        return self._ocr_engine
    
    def download_article(self, url: str) -> Dict:
        """
        下载微信公众号文章
        
        Args:
            url: 文章 URL
            
        Returns:
            包含 HTML 内容和元数据的字典
        """
        logger.info(f"正在下载文章: {url}")
        
        # 优先使用 requests 直接获取（更快，适合可以直接打开的链接）
        try:
            logger.info("使用 requests 直接获取...")
            response = self.session.get(url, timeout=30, allow_redirects=True)
            response.raise_for_status()
            
            # 检查是否被重定向到验证页面
            if 'wappoc_appmsgcaptcha' in response.url or 'poc_token' in response.url:
                logger.warning(f"检测到URL被重定向到验证页面: {response.url}，将使用 Playwright...")
                raise Exception("重定向到验证页面，需要使用浏览器")
            
            # 设置正确的编码
            if response.encoding and 'utf' in response.encoding.lower():
                response.encoding = 'utf-8'
            else:
                response.encoding = response.apparent_encoding or 'utf-8'
            
            html = response.text
            
            # 检查是否有验证页面内容
            if '环境异常' in html or '验证' in html or 'wappoc_appmsgcaptcha' in html:
                logger.warning("检测到验证页面内容，将使用 Playwright...")
                raise Exception("验证页面，需要使用浏览器")
            
            # 解析 HTML 提取元数据
            soup = BeautifulSoup(html, 'html.parser')
            title = soup.title.string if soup.title else ""
            
            meta_data = {}
            title_el = soup.select_one('#activity-name, .rich_media_title, h1')
            if title_el:
                meta_data['title'] = title_el.get_text(strip=True)
            
            author_el = soup.select_one('#meta_content .rich_media_meta_text, .profile_nickname')
            if author_el:
                meta_data['author'] = author_el.get_text(strip=True)
            
            date_el = soup.select_one('#publish_time, .publish_time')
            if date_el:
                meta_data['publish_time'] = date_el.get_text(strip=True)
            
            return {
                'html': html,
                'title': title,
                'meta': meta_data,
                'url': url
            }
            
        except Exception as e:
            logger.warning(f"requests 方法失败: {e}，尝试使用 Playwright...")
            
            # 只有在 requests 失败时才使用 Playwright
            
            # 使用 Playwright 获取完整页面（包括 JavaScript 渲染的内容）
            try:
                from playwright.sync_api import sync_playwright
                
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    context = browser.new_context(
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    )
                    page = context.new_page()
                    
                    try:
                        # 使用更宽松的等待条件，增加超时时间
                        page.goto(url, wait_until='networkidle', timeout=90000)
                        # 等待页面加载和可能的验证
                        time.sleep(8)
                        
                        # 检查是否有验证页面，如果有则等待更长时间
                        page_content = page.content()
                        retry_count = 0
                        while ('环境异常' in page_content or '验证' in page_content) and retry_count < 3:
                            logger.warning(f"检测到验证页面，等待更长时间... (尝试 {retry_count + 1}/3)")
                            time.sleep(15)
                            page.reload(wait_until='networkidle', timeout=90000)
                            time.sleep(8)
                            page_content = page.content()
                            retry_count += 1
                        
                        # 如果仍然有验证页面，尝试滚动页面触发加载
                        if '环境异常' in page_content or '验证' in page_content:
                            logger.warning("尝试滚动页面以触发内容加载...")
                            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            time.sleep(5)
                            page.evaluate("window.scrollTo(0, 0)")
                            time.sleep(3)
                            page_content = page.content()
                        
                        # 获取页面 HTML
                        html = page.content()
                        
                        # 提取标题
                        title = page.title()
                        
                        # 尝试从页面中提取更多元数据
                        meta_data = page.evaluate("""
                            () => {
                                const meta = {};
                                // 尝试提取文章标题
                                const titleEl = document.querySelector('#activity-name, .rich_media_title, h1');
                                if (titleEl) meta.title = titleEl.textContent.trim();
                                
                                // 尝试提取作者
                                const authorEl = document.querySelector('#meta_content .rich_media_meta_text, .profile_nickname');
                                if (authorEl) meta.author = authorEl.textContent.trim();
                                
                                // 尝试提取发布时间
                                const dateEl = document.querySelector('#publish_time, .publish_time');
                                if (dateEl) meta.publish_time = dateEl.textContent.trim();
                                
                                return meta;
                            }
                        """)
                        
                        browser.close()
                        
                        return {
                            'html': html,
                            'title': title,
                            'meta': meta_data,
                            'url': url
                        }
                        
                    except Exception as e2:
                        logger.error(f"Playwright 下载文章也失败: {e2}")
                        browser.close()
                        raise
            except ImportError:
                logger.error("Playwright 未安装，无法使用浏览器模式")
                raise
    
    def extract_images(self, html: str, base_url: str) -> List[Dict]:
        """
        从 HTML 中提取所有图片
        
        Args:
            html: HTML 内容
            base_url: 基础 URL（用于解析相对路径）
            
        Returns:
            图片信息列表
        """
        soup = BeautifulSoup(html, 'html.parser')
        images = []
        
        # 查找所有图片标签
        img_tags = soup.find_all('img')
        
        for idx, img in enumerate(img_tags):
            # 尝试多种可能的属性
            src = (img.get('src') or 
                   img.get('data-src') or 
                   img.get('data-original') or
                   img.get('data-lazy-src') or
                   img.get('data-url') or
                   img.get('data-img'))
            
            # 如果是 base64 图片，跳过
            if src and src.startswith('data:'):
                continue
            
            if not src:
                continue
            
            # 处理相对路径
            if src.startswith('//'):
                src = 'https:' + src
            elif src.startswith('/'):
                src = urljoin(base_url, src)
            elif not src.startswith('http'):
                src = urljoin(base_url, src)
            
            # 下载图片
            try:
                img_path = self._download_image(src, idx)
                if img_path:
                    images.append({
                        'index': idx,
                        'url': src,
                        'local_path': str(img_path),
                        'alt': img.get('alt', ''),
                        'title': img.get('title', '')
                    })
            except Exception as e:
                logger.warning(f"下载图片失败 {src}: {e}")
        
        logger.info(f"提取到 {len(images)} 张图片")
        return images
    
    def _download_image(self, url: str, index: int) -> Optional[Path]:
        """
        下载图片
        
        Args:
            url: 图片 URL
            index: 图片索引
            
        Returns:
            本地图片路径
        """
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # 确定文件扩展名
            parsed = urlparse(url)
            ext = os.path.splitext(parsed.path)[1] or '.jpg'
            if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                ext = '.jpg'
            
            # 保存图片
            img_path = self.images_dir / f"image_{index:03d}{ext}"
            with open(img_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"下载图片: {img_path}")
            return img_path
            
        except Exception as e:
            logger.error(f"下载图片失败 {url}: {e}")
            return None
    
    def ocr_image(self, image_path: str) -> str:
        """
        使用 OCR 识别图片中的文字
        
        Args:
            image_path: 图片路径
            
        Returns:
            识别出的文字
        """
        engine_type, engine = self._get_ocr_engine()
        
        if engine_type == 'paddleocr':
            try:
                # 使用 predict 方法（新 API）
                result = engine.predict(image_path)
                
                texts = []
                if result:
                    # PaddleOCR 新 API 返回格式: [OCRResult, ...]
                    # OCRResult 对象可以像字典一样访问，包含 'rec_texts' 字段
                    if isinstance(result, list) and len(result) > 0:
                        for ocr_result in result:
                            # OCRResult 对象支持字典式访问
                            if hasattr(ocr_result, 'get'):
                                rec_texts = ocr_result.get('rec_texts', [])
                            elif isinstance(ocr_result, dict):
                                rec_texts = ocr_result.get('rec_texts', [])
                            else:
                                # 尝试直接访问属性
                                rec_texts = getattr(ocr_result, 'rec_texts', [])
                            
                            if rec_texts:
                                texts.extend(rec_texts)
                
                text = '\n'.join(texts)
                if text.strip():
                    logger.info(f"OCR 识别完成 (PaddleOCR): {image_path}")
                    logger.debug(f"识别到 {len(texts)} 行文字: {text[:50]}...")
                    return text.strip()
                else:
                    logger.warning(f"PaddleOCR 未识别到文字: {image_path}")
            except Exception as e:
                logger.warning(f"PaddleOCR 识别失败: {e}")
                import traceback
                logger.debug(traceback.format_exc())
        
        elif engine_type == 'tesseract':
            try:
                img = Image.open(image_path)
                text = engine.image_to_string(img, lang='chi_sim+eng')
                if text.strip():
                    logger.info(f"OCR 识别完成 (Tesseract): {image_path}")
                    return text.strip()
            except Exception as e:
                logger.warning(f"Tesseract 识别失败: {e}")
        
        return ""
    
    def detect_text_region(self, image_path: str) -> Optional[Tuple[int, int, int, int]]:
        """
        检测图片中的文字区域（简单方法：假设文字在上半部分）
        
        Args:
            image_path: 图片路径
            
        Returns:
            文字区域坐标 (left, top, right, bottom) 或 None
        """
        try:
            img = Image.open(image_path)
            width, height = img.size
            
            # 简单策略：假设标题文字在上 1/3 区域
            # 可以根据实际情况调整
            top = 0
            bottom = height // 3
            left = 0
            right = width
            
            return (left, top, right, bottom)
        except Exception as e:
            logger.warning(f"检测文字区域失败: {e}")
            return None
    
    def crop_text_region(self, image_path: str, output_path: str, 
                        text_region: Optional[Tuple[int, int, int, int]] = None) -> Optional[Path]:
        """
        裁剪图片的文字区域
        
        Args:
            image_path: 原始图片路径
            output_path: 输出图片路径
            text_region: 文字区域坐标 (left, top, right, bottom)，如果为 None 则自动检测
            
        Returns:
            裁剪后的图片路径
        """
        try:
            img = Image.open(image_path)
            
            if text_region:
                # 使用指定的区域
                left, top, right, bottom = text_region
            else:
                # 自动检测文字区域
                region = self.detect_text_region(image_path)
                if region:
                    left, top, right, bottom = region
                else:
                    # 默认裁剪上半部分
                    width, height = img.size
                    left, top, right, bottom = 0, 0, width, height // 2
            
            # 裁剪图片
            cropped = img.crop((left, top, right, bottom))
            
            # 保存裁剪后的图片
            output = Path(output_path)
            cropped.save(output)
            
            logger.info(f"裁剪图片文字区域: {output}")
            return output
            
        except Exception as e:
            logger.error(f"裁剪图片失败 {image_path}: {e}")
            return None
    
    def extract_text_content(self, html: str) -> Dict:
        """
        从 HTML 中提取文本内容
        
        Args:
            html: HTML 内容
            
        Returns:
            包含标题、正文等内容的字典
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # 提取标题
        title = None
        title_selectors = [
            '#activity-name', 
            '.rich_media_title', 
            'h1',
            'h2[id="activity-name"]',
            '.profile_nickname + h1',
            'meta[property="og:title"]'
        ]
        for selector in title_selectors:
            try:
                title_el = soup.select_one(selector)
                if title_el:
                    if selector.startswith('meta'):
                        title = title_el.get('content', '').strip()
                    else:
                        title = title_el.get_text(strip=True)
                    if title:
                        break
            except:
                continue
        
        # 提取正文 - 尝试多种选择器
        content = None
        content_selectors = [
            '#js_content',
            '#js_article',
            '.rich_media_content',
            'article',
            '.article-content',
            '[id*="content"]',
            '[class*="content"]'
        ]
        for selector in content_selectors:
            try:
                content_el = soup.select_one(selector)
                if content_el:
                    # 检查是否有实际内容
                    text_preview = content_el.get_text(strip=True)[:100]
                    if len(text_preview) > 20:  # 确保有足够的内容
                        content = content_el
                        break
            except:
                continue
        
        # 提取段落文本
        paragraphs = []
        if content:
            # 先提取所有段落
            for p in content.find_all('p'):
                text = p.get_text(strip=True)
                # 过滤太短的文本、空白、特殊字符
                if text and len(text) > 3 and not text.isspace():
                    # 过滤掉明显的非内容文本
                    if not any(skip in text for skip in ['var ', 'function', 'javascript:', 'style=', 'class=']):
                        paragraphs.append(text)
            
            # 如果没有段落，尝试提取 span 和 div 中的文本
            if not paragraphs:
                for tag in content.find_all(['span', 'div', 'section']):
                    text = tag.get_text(strip=True)
                    # 过滤太短的文本和可能的样式/脚本内容
                    if (text and len(text) > 10 and 
                        not text.startswith('var ') and 
                        'function' not in text and
                        not text.startswith('http') and
                        not text.isspace()):
                        # 检查是否是重复内容
                        if not any(p == text for p in paragraphs):
                            paragraphs.append(text)
            
            # 提取标题（h1-h6）
            for h in content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                text = h.get_text(strip=True)
                if text and len(text) > 2:
                    # 避免重复
                    header_text = f"## {text}"
                    if header_text not in paragraphs:
                        paragraphs.append(header_text)
            
            # 提取列表项
            for li in content.find_all(['li', 'dt', 'dd']):
                text = li.get_text(strip=True)
                if text and len(text) > 5:
                    paragraphs.append(f"- {text}")
        
        # 如果还是没有内容，尝试从整个页面提取
        if not paragraphs:
            logger.warning("未找到正文内容，尝试从整个页面提取...")
            # 尝试提取所有可见文本
            body = soup.find('body')
            if body:
                # 先尝试提取 script 标签中的 JSON 数据（微信公众号文章内容可能在 script 中）
                scripts = body.find_all('script')
                for script in scripts:
                    script_text = script.string
                    if script_text and ('msgList' in script_text or 'content' in script_text):
                        # 尝试提取 JSON 数据
                        try:
                            import json
                            import re
                            # 查找 JSON 对象
                            json_match = re.search(r'\{[^{}]*"content"[^{}]*\}', script_text, re.DOTALL)
                            if json_match:
                                # 尝试解析 JSON
                                try:
                                    data = json.loads(json_match.group())
                                    if 'content' in data:
                                        content_html = data['content']
                                        content_soup = BeautifulSoup(content_html, 'html.parser')
                                        for p in content_soup.find_all('p'):
                                            text = p.get_text(strip=True)
                                            if text and len(text) > 5:
                                                paragraphs.append(text)
                                except:
                                    pass
                        except:
                            pass
                
                # 如果还是没有，尝试从 script 标签中提取 msgList 或类似数据
                if not paragraphs:
                    import json
                    import re
                    # 查找 msgList 或 msg_title 等变量
                    for script in scripts:
                        if script.string:
                            script_text = script.string
                            # 查找 msgList 变量
                            msg_list_match = re.search(r'var\s+msgList\s*=\s*(\[.*?\]);', script_text, re.DOTALL)
                            if msg_list_match:
                                try:
                                    msg_list = json.loads(msg_list_match.group(1))
                                    if isinstance(msg_list, list) and len(msg_list) > 0:
                                        msg = msg_list[0]
                                        # 提取标题
                                        if 'msg_title' in msg:
                                            title = msg['msg_title']
                                        # 提取内容
                                        if 'content' in msg:
                                            content_html = msg['content']
                                            content_soup = BeautifulSoup(content_html, 'html.parser')
                                            for p in content_soup.find_all('p'):
                                                text = p.get_text(strip=True)
                                                if text and len(text) > 5:
                                                    paragraphs.append(text)
                                except Exception as e:
                                    logger.debug(f"解析 msgList 失败: {e}")
                            
                            # 查找其他可能的 JSON 数据
                            json_matches = re.findall(r'\{[^{}]*"(?:title|content|msg_title|msg_content)"[^{}]*\}', script_text, re.DOTALL)
                            for json_str in json_matches:
                                try:
                                    data = json.loads(json_str)
                                    if 'content' in data or 'msg_content' in data:
                                        content_html = data.get('content') or data.get('msg_content', '')
                                        if content_html:
                                            content_soup = BeautifulSoup(content_html, 'html.parser')
                                            for p in content_soup.find_all('p'):
                                                text = p.get_text(strip=True)
                                                if text and len(text) > 5:
                                                    paragraphs.append(text)
                                except:
                                    pass
                
                # 如果还是没有，提取所有文本
                if not paragraphs:
                    all_text = body.get_text(separator='\n', strip=True)
                    # 按行分割，过滤空行和太短的行
                    lines = [line.strip() for line in all_text.split('\n') 
                            if line.strip() and len(line.strip()) > 10]
                    # 过滤掉明显的非内容文本
                    filtered_lines = []
                    for line in lines:
                        if (not line.startswith('var ') and 
                            'function' not in line and 
                            not line.startswith('http') and
                            'javascript:' not in line and
                            'style=' not in line and
                            len(line) > 15 and
                            any('\u4e00' <= c <= '\u9fff' for c in line)):  # 必须包含中文
                            filtered_lines.append(line)
                    paragraphs = filtered_lines[:200]  # 增加限制数量
        
        logger.info(f"提取到 {len(paragraphs)} 个段落，标题: {title}")
        
        return {
            'title': title,
            'paragraphs': paragraphs,
            'raw_html': str(content) if content else None
        }
    
    def convert_to_markdown(self, article_data: Dict, images: List[Dict], 
                           first_image_text: str = "", first_image_cropped: str = "") -> str:
        """
        转换为 Markdown 格式
        
        Args:
            article_data: 文章数据
            images: 图片列表
            first_image_text: 第一张图片的 OCR 文字
            first_image_cropped: 第一张图片裁剪后的路径
            
        Returns:
            Markdown 内容
        """
        md_lines = []
        
        # Front matter
        title_text = (article_data.get("title") or 
                     article_data.get("meta", {}).get("title") or 
                     "未命名文章")
        md_lines.append("---")
        md_lines.append(f'title: "{title_text}"')
        md_lines.append(f'date: {datetime.now().strftime("%Y-%m-%d")}')
        md_lines.append(f'permalink: /posts/{datetime.now().strftime("%Y/%m")}/wechat-article')
        md_lines.append(f'author: {article_data.get("meta", {}).get("author", "未知")}')
        excerpt_text = title_text[:100] if len(title_text) > 100 else title_text
        md_lines.append(f'excerpt: \'{excerpt_text}...\'')
        md_lines.append("tags:")
        md_lines.append("   - 转载")
        md_lines.append("   - 微信公众号")
        md_lines.append("---")
        md_lines.append("")
        
        # 如果有第一张图片的裁剪版本，先插入
        if first_image_cropped:
            rel_path = os.path.relpath(first_image_cropped, self.output_dir)
            md_lines.append(f"![文章标题图]({rel_path})")
            md_lines.append("")
        
        # 如果有 OCR 识别的文字，添加
        if first_image_text:
            md_lines.append("## 文章标题")
            md_lines.append("")
            md_lines.append(first_image_text)
            md_lines.append("")
        
        # 添加正文段落
        paragraphs = article_data.get('paragraphs', [])
        if paragraphs:
            md_lines.append("## 正文")
            md_lines.append("")
            for para in paragraphs:
                md_lines.append(para)
                md_lines.append("")
        
        # 添加其他图片
        if len(images) > 1:
            md_lines.append("## 配图")
            md_lines.append("")
            for img in images[1:]:  # 跳过第一张（已经在前面插入）
                rel_path = os.path.relpath(img['local_path'], self.output_dir)
                alt = img.get('alt', f"图片 {img['index']}")
                md_lines.append(f"![{alt}]({rel_path})")
                md_lines.append("")
        
        return "\n".join(md_lines)
    
    def process_article(self, url: str) -> str:
        """
        处理整篇文章：下载、提取、OCR、转换
        
        Args:
            url: 文章 URL
            
        Returns:
            Markdown 文件路径
        """
        # 1. 下载文章
        article_data = self.download_article(url)
        
        # 2. 提取图片
        images = self.extract_images(article_data['html'], url)
        
        # 3. 处理第一张图片
        first_image_text = ""
        first_image_cropped = ""
        if images:
            first_img = images[0]
            # OCR 识别
            first_image_text = self.ocr_image(first_img['local_path'])
            if first_image_text:
                logger.info(f"第一张图片 OCR 结果: {first_image_text[:100]}...")
            
            # 裁剪文字部分
            cropped_path = self.images_dir / f"image_000_cropped.jpg"
            cropped = self.crop_text_region(
                first_img['local_path'],
                str(cropped_path),
                text_region=None  # 自动检测
            )
            if cropped:
                first_image_cropped = str(cropped)
        
        # 4. 提取文本内容
        text_content = self.extract_text_content(article_data['html'])
        article_data.update(text_content)
        
        # 5. 转换为 Markdown
        md_content = self.convert_to_markdown(
            article_data,
            images,
            first_image_text,
            first_image_cropped
        )
        
        # 6. 保存 Markdown 文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        md_file = self.output_dir / f"article_{timestamp}.md"
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logger.info(f"Markdown 文件已保存: {md_file}")
        return str(md_file)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='提取微信公众号文章并转换为 Markdown')
    parser.add_argument('url', help='微信公众号文章 URL')
    parser.add_argument('-o', '--output', default='extracted_articles', 
                       help='输出目录（默认: extracted_articles）')
    
    args = parser.parse_args()
    
    extractor = WeChatArticleExtractor(output_dir=args.output)
    md_file = extractor.process_article(args.url)
    
    print(f"\n✅ 处理完成！")
    print(f"📄 Markdown 文件: {md_file}")
    print(f"🖼️  图片目录: {extractor.images_dir}")


if __name__ == '__main__':
    main()

