#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从微信公众号文章中提取所有链接
"""

import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Set
from urllib.parse import urljoin, urlparse, urlunparse
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LinkExtractor:
    """链接提取器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def fetch_page(self, url: str, use_playwright: bool = True) -> str:
        """
        获取网页内容
        
        Args:
            url: 网页URL
            use_playwright: 是否优先使用Playwright（对于需要JS渲染的页面）
            
        Returns:
            HTML内容
        """
        logger.info(f"正在获取网页: {url}")
        
        # 对于微信公众号文章，优先使用Playwright以确保获取完整内容
        if use_playwright:
            try:
                return self._fetch_with_playwright(url)
            except Exception as e:
                logger.warning(f"Playwright获取失败: {e}，尝试使用requests...")
        
        try:
            response = self.session.get(url, timeout=30, allow_redirects=True)
            response.raise_for_status()
            # 优先使用UTF-8编码，如果检测失败则使用apparent_encoding
            if response.encoding and 'utf' in response.encoding.lower():
                response.encoding = 'utf-8'
            else:
                response.encoding = response.apparent_encoding or 'utf-8'
            # 确保返回的是正确的Unicode字符串
            html = response.text
            if isinstance(html, bytes):
                html = html.decode('utf-8', errors='ignore')
            return html
        except requests.exceptions.RequestException as e:
            logger.error(f"获取网页失败: {e}")
            raise
    
    def _fetch_with_playwright(self, url: str) -> str:
        """使用Playwright获取网页内容（需要JS渲染时）"""
        try:
            from playwright.sync_api import sync_playwright
            
            logger.info("使用Playwright获取网页（支持JS渲染）...")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                # 设置用户代理
                page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                })
                page.goto(url, wait_until='networkidle', timeout=60000)
                # 等待页面完全加载
                page.wait_for_timeout(2000)
                html = page.content()
                browser.close()
                # 确保HTML是UTF-8编码的字符串
                if isinstance(html, bytes):
                    html = html.decode('utf-8', errors='ignore')
                return html
        except ImportError:
            logger.warning("Playwright未安装，无法使用JS渲染")
            raise
        except Exception as e:
            logger.error(f"Playwright获取失败: {e}")
            raise
    
    def extract_links(self, html: str, base_url: str) -> Dict[str, List[str]]:
        """
        从HTML中提取所有链接
        
        Args:
            html: HTML内容
            base_url: 基础URL，用于解析相对链接
            
        Returns:
            包含不同类型链接的字典
        """
        # 确保HTML以UTF-8编码处理
        if isinstance(html, bytes):
            html = html.decode('utf-8', errors='ignore')
        # 尝试使用lxml解析器（如果可用），否则使用html.parser
        try:
            soup = BeautifulSoup(html, 'lxml')
        except:
            soup = BeautifulSoup(html, 'html.parser')
        
        links = {
            'all_links': [],  # 所有链接
            'external_links': [],  # 外部链接
            'internal_links': [],  # 内部链接（同域名）
            'wechat_links': [],  # 微信公众号链接
            'http_links': [],  # HTTP/HTTPS链接
            'other_links': []  # 其他类型链接（如mailto, tel等）
        }
        
        # 解析基础URL
        base_parsed = urlparse(base_url)
        base_domain = base_parsed.netloc
        
        # 提取所有<a>标签中的链接
        for tag in soup.find_all('a', href=True):
            href = tag.get('href', '').strip()
            if not href:
                continue
            
            # 转换为绝对URL
            absolute_url = urljoin(base_url, href)
            parsed = urlparse(absolute_url)
            
            # 提取链接文本，确保正确处理中文编码
            try:
                # 尝试多种方法提取文本
                link_text = tag.string
                if not link_text:
                    link_text = tag.get_text(strip=True)
                if not link_text:
                    # 尝试从所有子节点提取
                    link_text = ''.join(tag.stripped_strings)
                if not link_text:
                    link_text = href
                
                # 确保文本是Unicode字符串
                if isinstance(link_text, bytes):
                    # 尝试多种编码
                    for encoding in ['utf-8', 'gbk', 'gb2312', 'latin1']:
                        try:
                            link_text = link_text.decode(encoding)
                            break
                        except:
                            continue
                    else:
                        link_text = link_text.decode('utf-8', errors='ignore')
                
                # 清理文本中的特殊字符
                link_text = link_text.replace('\n', ' ').replace('\r', ' ').strip()
                
                # 修复常见的编码错误：UTF-8被错误地以Latin1解码
                # 如果文本包含典型的乱码字符（如ä, å, ç等），尝试修复
                if link_text and any(c in link_text for c in ['ä', 'å', 'ç', 'è', 'é', 'ê', 'ë', 'ì', 'í', 'î', 'ï']):
                    try:
                        # 尝试将Latin1编码的文本重新编码为字节，然后以UTF-8解码
                        fixed = link_text.encode('latin1', errors='ignore').decode('utf-8', errors='ignore')
                        # 如果修复后的文本包含中文字符，说明修复成功
                        if fixed and any('\u4e00' <= c <= '\u9fff' for c in fixed):
                            link_text = fixed
                    except:
                        pass
                        
            except Exception as e:
                logger.warning(f"提取链接文本失败: {e}, 使用href作为文本")
                link_text = href
            
            link_info = {
                'url': absolute_url,
                'text': link_text,
                'href': href
            }
            
            links['all_links'].append(link_info)
            
            # 分类链接
            if parsed.scheme in ['http', 'https']:
                links['http_links'].append(link_info)
                
                # 判断是否为外部链接
                if parsed.netloc and parsed.netloc != base_domain:
                    links['external_links'].append(link_info)
                else:
                    links['internal_links'].append(link_info)
                
                # 判断是否为微信公众号链接
                if 'mp.weixin.qq.com' in parsed.netloc:
                    links['wechat_links'].append(link_info)
            else:
                links['other_links'].append(link_info)
        
        # 提取其他可能的链接（如script中的URL、data属性等）
        # 提取script标签中的URL
        for script in soup.find_all('script'):
            if script.string:
                # 查找URL模式
                urls = re.findall(r'https?://[^\s"\'<>]+', script.string)
                for url in urls:
                    # 检查是否已存在
                    existing_urls = {link['url'] for link in links['all_links']}
                    if url not in existing_urls:
                        parsed = urlparse(url)
                        if parsed.scheme in ['http', 'https']:
                            link_info = {
                                'url': url,
                                'text': '',
                                'href': url,
                                'source': 'script'
                            }
                            links['all_links'].append(link_info)
                            links['http_links'].append(link_info)
                            
                            # 判断是否为外部链接
                            if parsed.netloc and parsed.netloc != base_domain:
                                links['external_links'].append(link_info)
                            else:
                                links['internal_links'].append(link_info)
                            
                            # 判断是否为微信公众号链接
                            if 'mp.weixin.qq.com' in parsed.netloc:
                                links['wechat_links'].append(link_info)
        
        # 去重（基于URL）- 每个类别独立去重
        for category in links:
            seen_urls: Set[str] = set()
            unique_links = []
            for link in links[category]:
                if link['url'] not in seen_urls:
                    seen_urls.add(link['url'])
                    unique_links.append(link)
            links[category] = unique_links
        
        return links
    
    def save_links(self, links: Dict[str, List[str]], output_file: Path, source_url: str):
        """
        保存链接到文件
        
        Args:
            links: 链接字典
            output_file: 输出文件路径
            source_url: 源URL
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# 链接提取报告\n\n")
            f.write(f"**源URL**: {source_url}\n\n")
            f.write(f"**提取时间**: {timestamp}\n\n")
            f.write(f"---\n\n")
            
            # 统计信息
            f.write(f"## 统计信息\n\n")
            f.write(f"- 总链接数: {len(links['all_links'])}\n")
            f.write(f"- HTTP/HTTPS链接: {len(links['http_links'])}\n")
            f.write(f"- 外部链接: {len(links['external_links'])}\n")
            f.write(f"- 内部链接: {len(links['internal_links'])}\n")
            f.write(f"- 微信公众号链接: {len(links['wechat_links'])}\n")
            f.write(f"- 其他链接: {len(links['other_links'])}\n")
            f.write(f"\n---\n\n")
            
            # 所有链接
            f.write(f"## 所有链接\n\n")
            for i, link in enumerate(links['all_links'], 1):
                text = link['text'] if link['text'] else '(无文本)'
                source = f" (来源: {link.get('source', 'a标签')})" if link.get('source') else ""
                f.write(f"{i}. [{text}]({link['url']}){source}\n")
                f.write(f"   - URL: {link['url']}\n")
                if link['href'] != link['url']:
                    f.write(f"   - 原始href: {link['href']}\n")
                f.write(f"\n")
            
            f.write(f"\n---\n\n")
            
            # 分类链接
            if links['wechat_links']:
                f.write(f"## 微信公众号链接\n\n")
                for i, link in enumerate(links['wechat_links'], 1):
                    text = link['text'] if link['text'] else '(无文本)'
                    f.write(f"{i}. [{text}]({link['url']})\n")
                f.write(f"\n---\n\n")
            
            if links['external_links']:
                f.write(f"## 外部链接\n\n")
                for i, link in enumerate(links['external_links'], 1):
                    text = link['text'] if link['text'] else '(无文本)'
                    f.write(f"{i}. [{text}]({link['url']})\n")
                f.write(f"\n---\n\n")
            
            if links['internal_links']:
                f.write(f"## 内部链接\n\n")
                for i, link in enumerate(links['internal_links'], 1):
                    text = link['text'] if link['text'] else '(无文本)'
                    f.write(f"{i}. [{text}]({link['url']})\n")
                f.write(f"\n---\n\n")
            
            if links['other_links']:
                f.write(f"## 其他链接\n\n")
                for i, link in enumerate(links['other_links'], 1):
                    text = link['text'] if link['text'] else '(无文本)'
                    f.write(f"{i}. [{text}]({link['url']})\n")
                f.write(f"\n---\n\n")
            
            # JSON格式（便于程序处理）
            f.write(f"## JSON格式数据\n\n")
            f.write(f"```json\n")
            json.dump(links, f, ensure_ascii=False, indent=2)
            f.write(f"\n```\n")
        
        logger.info(f"链接已保存到: {output_file}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='从网页中提取所有链接')
    parser.add_argument('url', help='网页URL')
    parser.add_argument('-o', '--output', help='输出文件路径（默认: extracted_articles/links_YYYYMMDD_HHMMSS.md）')
    
    args = parser.parse_args()
    
    extractor = LinkExtractor()
    
    try:
        # 获取网页内容
        html = extractor.fetch_page(args.url)
        
        # 提取链接
        links = extractor.extract_links(html, args.url)
        
        # 确定输出文件
        if args.output:
            output_file = Path(args.output)
        else:
            output_dir = Path('extracted_articles')
            output_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = output_dir / f"links_{timestamp}.md"
        
        # 保存链接
        extractor.save_links(links, output_file, args.url)
        
        print(f"\n✅ 链接提取完成！")
        print(f"📄 输出文件: {output_file}")
        print(f"📊 统计:")
        print(f"   - 总链接数: {len(links['all_links'])}")
        print(f"   - HTTP/HTTPS链接: {len(links['http_links'])}")
        print(f"   - 微信公众号链接: {len(links['wechat_links'])}")
        print(f"   - 外部链接: {len(links['external_links'])}")
        
    except Exception as e:
        logger.error(f"处理失败: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())

