#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成完整的微信公众号文章 Markdown
提取所有图片的 OCR 文字，并按照参考格式组织内容
"""

import os
import re
from pathlib import Path
from typing import List, Dict
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.extract_wechat_article import WeChatArticleExtractor


def extract_all_image_texts(extractor: WeChatArticleExtractor, images_dir: Path) -> List[Dict]:
    """提取所有图片的文字内容"""
    image_texts = []
    
    # 获取所有图片文件（按文件名排序）
    image_files = sorted(images_dir.glob("image_*.jpg"))
    
    for img_path in image_files:
        # 跳过裁剪版本
        if 'cropped' in img_path.name:
            continue
        
        print(f"正在识别图片: {img_path.name}...")
        text = extractor.ocr_image(str(img_path))
        
        if text:
            image_texts.append({
                'image': img_path.name,
                'text': text,
                'index': int(re.search(r'image_(\d+)', img_path.name).group(1)) if re.search(r'image_(\d+)', img_path.name) else 0
            })
            print(f"  识别到 {len(text)} 个字符")
        else:
            print(f"  未识别到文字")
    
    return sorted(image_texts, key=lambda x: x['index'])


def organize_content(image_texts: List[Dict], article_data: Dict) -> str:
    """按照参考格式组织内容"""
    md_lines = []
    
    # Front matter
    title = article_data.get("title") or article_data.get("meta", {}).get("title") or "未命名文章"
    author = article_data.get("meta", {}).get("author", "未知")
    
    md_lines.append("---")
    md_lines.append(f'title: "{title}"')
    md_lines.append(f'date: {datetime.now().strftime("%Y-%m-%d")}')
    md_lines.append(f'permalink: /posts/{datetime.now().strftime("%Y/%m")}/wechat-article')
    md_lines.append(f'author: {author}')
    md_lines.append(f'excerpt: \'{title[:100]}...\'')
    md_lines.append("tags:")
    md_lines.append("   - 转载")
    md_lines.append("   - 微信公众号")
    md_lines.append("   - 数学")
    md_lines.append("   - 数值计算")
    md_lines.append("---")
    md_lines.append("")
    
    # 引言
    if image_texts:
        first_text = image_texts[0].get('text', '')
        if first_text:
            # 提取标题图
            md_lines.append(f"![文章标题图](images/image_000_cropped.jpg)")
            md_lines.append("")
            md_lines.append(first_text)
            md_lines.append("")
    
    # 正文内容 - 根据图片文字组织
    if len(image_texts) > 1:
        md_lines.append("## 正文内容")
        md_lines.append("")
        
        for i, img_data in enumerate(image_texts[1:], 1):
            img_name = img_data['image']
            text = img_data['text']
            
            # 插入图片
            md_lines.append(f"![配图 {i}](images/{img_name})")
            md_lines.append("")
            
            # 插入 OCR 识别的文字
            if text and len(text.strip()) > 5:
                # 清理文字（移除多余空白）
                cleaned_text = re.sub(r'\s+', ' ', text.strip())
                md_lines.append(cleaned_text)
                md_lines.append("")
    
    # 如果图片文字较少，尝试从 HTML 提取
    paragraphs = article_data.get('paragraphs', [])
    if paragraphs:
        md_lines.append("## 补充说明")
        md_lines.append("")
        for para in paragraphs:
            md_lines.append(para)
            md_lines.append("")
    
    return "\n".join(md_lines)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='生成完整的微信公众号文章 Markdown')
    parser.add_argument('-i', '--input-dir', default='extracted_articles',
                       help='输入目录（默认: extracted_articles）')
    parser.add_argument('-o', '--output', default='extracted_articles/article_20251106_203830.md',
                       help='输出文件（默认: extracted_articles/article_20251106_203830.md）')
    
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    images_dir = input_dir / "images"
    output_file = Path(args.output)
    
    # 初始化提取器
    extractor = WeChatArticleExtractor(output_dir=str(input_dir))
    
    # 读取已有的文章数据
    article_data = {
        'title': '牛顿迭代和稀疏矩阵：Krylov-Multigrid的前传',
        'meta': {
            'author': '杨晨',
            'title': '牛顿迭代和稀疏矩阵：Krylov-Multigrid的前传'
        },
        'paragraphs': []
    }
    
    # 提取所有图片的文字
    print("=" * 50)
    print("开始提取所有图片的文字内容...")
    print("=" * 50)
    image_texts = extract_all_image_texts(extractor, images_dir)
    
    print(f"\n共提取到 {len(image_texts)} 张图片的文字")
    
    # 组织内容
    print("\n正在生成 Markdown 文件...")
    md_content = organize_content(image_texts, article_data)
    
    # 保存文件
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"\n✅ 完成！")
    print(f"📄 Markdown 文件: {output_file}")
    print(f"📊 包含 {len(image_texts)} 张图片的文字内容")


if __name__ == '__main__':
    main()

