#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量下载微信公众号文章
从链接文件中提取所有URL并下载文章
"""

import re
import sys
import time
import logging
from pathlib import Path
from typing import List, Dict, Set
from urllib.parse import urlparse
from datetime import datetime

# 导入现有的文章提取器
sys.path.insert(0, str(Path(__file__).parent))
from extract_wechat_article import WeChatArticleExtractor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_urls_from_markdown(file_path: Path) -> List[Dict[str, str]]:
    """
    从Markdown文件中提取所有链接
    
    Args:
        file_path: Markdown文件路径
        
    Returns:
        包含URL和标题的字典列表
    """
    urls = []
    seen_urls: Set[str] = set()
    
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        logger.error(f"读取文件失败: {e}")
        return urls
    
    # 匹配Markdown链接格式: [text](url)
    pattern = r'\[([^\]]+)\]\((https?://[^\)]+)\)'
    matches = re.findall(pattern, content)
    
    for text, url in matches:
        # 只处理微信公众号文章链接
        if 'mp.weixin.qq.com' in url:
            # 清理URL（移除fragment等）
            parsed = urlparse(url)
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                clean_url += f"?{parsed.query}"
            
            # 去重
            if clean_url not in seen_urls:
                seen_urls.add(clean_url)
                urls.append({
                    'url': clean_url,
                    'title': text.strip(),
                    'original_url': url
                })
    
    logger.info(f"从文件中提取到 {len(urls)} 个微信公众号文章链接")
    return urls


def batch_download_articles(
    links_file: Path,
    output_dir: str = "extracted_articles",
    delay: float = 2.0,
    max_retries: int = 3,
    start_index: int = 0,
    end_index: int = None
):
    """
    批量下载文章
    
    Args:
        links_file: 包含链接的Markdown文件路径
        output_dir: 输出目录
        delay: 每次下载之间的延迟（秒）
        max_retries: 最大重试次数
        start_index: 开始索引（用于断点续传）
        end_index: 结束索引（None表示到末尾）
    """
    # 提取URL
    urls = extract_urls_from_markdown(links_file)
    
    if not urls:
        logger.error("未找到任何有效的微信公众号文章链接")
        return
    
    # 限制范围
    if end_index is None:
        end_index = len(urls)
    urls = urls[start_index:end_index]
    
    logger.info(f"准备下载 {len(urls)} 篇文章（索引 {start_index} 到 {end_index-1}）")
    
    # 创建提取器（确保输出目录存在）
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    extractor = WeChatArticleExtractor(output_dir=str(output_path))
    
    # 统计信息
    success_count = 0
    failed_count = 0
    failed_urls = []
    
    # 创建下载记录文件
    download_log = Path(output_dir) / "download_log.txt"
    download_log.parent.mkdir(parents=True, exist_ok=True)
    
    # 读取已下载的URL（用于跳过）
    downloaded_urls: Set[str] = set()
    if download_log.exists():
        try:
            with open(download_log, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        downloaded_urls.add(line.strip())
            logger.info(f"发现 {len(downloaded_urls)} 个已下载的URL，将跳过")
        except Exception as e:
            logger.warning(f"读取下载记录失败: {e}")
    
    # 批量下载
    start_time = datetime.now()
    
    with open(download_log, 'a', encoding='utf-8') as log_file:
        # 写入开始标记
        log_file.write(f"\n# 批量下载开始: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_file.write(f"# 总计: {len(urls)} 篇文章\n\n")
        
        for i, url_info in enumerate(urls, 1):
            url = url_info['url']
            title = url_info['title']
            
            # 检查是否已下载
            if url in downloaded_urls:
                logger.info(f"[{i}/{len(urls)}] 跳过已下载: {title[:50]}...")
                continue
            
            logger.info(f"[{i}/{len(urls)}] 开始下载: {title[:50]}...")
            logger.info(f"URL: {url}")
            
            # 下载文章
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    md_file = extractor.process_article(url)
                    logger.info(f"✅ 下载成功: {md_file}")
                    success = True
                    success_count += 1
                    
                    # 记录到日志
                    log_file.write(f"{url}\n")
                    log_file.flush()
                    downloaded_urls.add(url)
                    
                except Exception as e:
                    retry_count += 1
                    logger.error(f"❌ 下载失败 (尝试 {retry_count}/{max_retries}): {e}")
                    
                    if retry_count < max_retries:
                        wait_time = delay * retry_count
                        logger.info(f"等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                    else:
                        failed_count += 1
                        failed_urls.append({
                            'url': url,
                            'title': title,
                            'error': str(e)
                        })
                        logger.error(f"最终失败: {url}")
            
            # 延迟，避免请求过快
            if i < len(urls) and success:
                logger.info(f"等待 {delay} 秒...")
                time.sleep(delay)
    
    # 输出统计信息
    end_time = datetime.now()
    duration = end_time - start_time
    
    logger.info("\n" + "="*60)
    logger.info("批量下载完成！")
    logger.info(f"总文章数: {len(urls)}")
    logger.info(f"成功: {success_count}")
    logger.info(f"失败: {failed_count}")
    logger.info(f"已跳过: {len(downloaded_urls) - success_count}")
    logger.info(f"总耗时: {duration}")
    logger.info("="*60)
    
    # 保存失败列表
    if failed_urls:
        failed_file = Path(output_dir) / "failed_downloads.txt"
        with open(failed_file, 'w', encoding='utf-8') as f:
            f.write(f"# 下载失败的文章列表\n")
            f.write(f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            for item in failed_urls:
                f.write(f"## {item['title']}\n")
                f.write(f"URL: {item['url']}\n")
                f.write(f"错误: {item['error']}\n\n")
        logger.info(f"失败列表已保存到: {failed_file}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='批量下载微信公众号文章')
    parser.add_argument('links_file', help='包含链接的Markdown文件路径')
    parser.add_argument('-o', '--output', default='extracted_articles',
                       help='输出目录（默认: extracted_articles）')
    parser.add_argument('-d', '--delay', type=float, default=2.0,
                       help='每次下载之间的延迟（秒，默认: 2.0）')
    parser.add_argument('-r', '--retries', type=int, default=3,
                       help='最大重试次数（默认: 3）')
    parser.add_argument('--start', type=int, default=0,
                       help='开始索引（默认: 0）')
    parser.add_argument('--end', type=int, default=None,
                       help='结束索引（默认: 到末尾）')
    
    args = parser.parse_args()
    
    links_file = Path(args.links_file)
    if not links_file.exists():
        logger.error(f"文件不存在: {links_file}")
        return 1
    
    try:
        batch_download_articles(
            links_file=links_file,
            output_dir=args.output,
            delay=args.delay,
            max_retries=args.retries,
            start_index=args.start,
            end_index=args.end
        )
        return 0
    except KeyboardInterrupt:
        logger.info("\n用户中断下载")
        return 1
    except Exception as e:
        logger.error(f"批量下载失败: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit(main())

