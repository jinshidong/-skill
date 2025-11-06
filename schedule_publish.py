#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时发表脚本

支持定时发表微信公众号文章，可以设置发表时间和 Markdown 文件。
"""

import sys
import time
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# 添加 src 目录到路径
src_path = str(Path(__file__).parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from wechat_publisher import publish_from_markdown  # type: ignore

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ScheduledPublisher:
    """定时发表器"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        初始化定时发表器
        
        Args:
            config_file: 配置文件路径（JSON 格式）
        """
        self.config_file = config_file
        self.tasks = []
        
        if config_file:
            self.load_config(config_file)
    
    def load_config(self, config_file: str):
        """
        从配置文件加载任务
        
        配置文件格式：
        {
            "tasks": [
                {
                    "md_file": "path/to/article.md",
                    "publish_time": "2024-01-01 12:00:00",
                    "style": "academic_gray",
                    "user_data_dir": "./tmp_profile",
                    "clear_editor": true,
                    "auto_publish": false
                }
            ]
        }
        """
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            self.tasks = config.get("tasks", [])
            logger.info(f"从配置文件加载了 {len(self.tasks)} 个任务")
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            raise
    
    def add_task(
        self,
        md_file: str,
        publish_time: str,
        style: str = "academic_gray",
        user_data_dir: str = "./tmp_profile",
        clear_editor: bool = True,
        auto_publish: bool = False
    ):
        """
        添加发表任务
        
        Args:
            md_file: Markdown 文件路径
            publish_time: 发表时间（格式：YYYY-MM-DD HH:MM:SS）
            style: HTML 风格
            user_data_dir: 浏览器用户数据目录
            clear_editor: 是否先清空编辑器
            auto_publish: 是否自动发表
        """
        try:
            publish_dt = datetime.strptime(publish_time, "%Y-%m-%d %H:%M:%S")
            task = {
                "md_file": md_file,
                "publish_time": publish_time,
                "publish_datetime": publish_dt,
                "style": style,
                "user_data_dir": user_data_dir,
                "clear_editor": clear_editor,
                "auto_publish": auto_publish
            }
            self.tasks.append(task)
            logger.info(f"添加任务: {md_file} -> {publish_time}")
        except ValueError as e:
            logger.error(f"发表时间格式错误: {e}")
            raise
    
    def run(self, check_interval: int = 60):
        """
        运行定时发表器
        
        Args:
            check_interval: 检查间隔（秒）
        """
        logger.info(f"定时发表器启动，检查间隔: {check_interval} 秒")
        logger.info(f"当前有 {len(self.tasks)} 个待发表任务")
        
        while self.tasks:
            now = datetime.now()
            completed_tasks = []
            
            for task in self.tasks:
                publish_dt = task["publish_datetime"]
                
                # 检查是否到了发表时间
                if now >= publish_dt:
                    logger.info(f"开始发表任务: {task['md_file']} (计划时间: {task['publish_time']})")
                    
                    try:
                        result = publish_from_markdown(
                            md_file=task["md_file"],
                            user_data_dir=task["user_data_dir"],
                            style=task["style"],
                            headless=False,  # 定时发表建议显示浏览器
                            clear_editor=task["clear_editor"],
                            auto_publish=task["auto_publish"]
                        )
                        
                        if result.get("ok"):
                            logger.info(f"任务发表成功: {task['md_file']}")
                        else:
                            logger.error(f"任务发表失败: {task['md_file']}, 错误: {result.get('error')}")
                        
                        completed_tasks.append(task)
                    except Exception as e:
                        logger.error(f"执行任务时出错: {e}", exc_info=True)
                        completed_tasks.append(task)
                else:
                    # 计算剩余时间
                    remaining = (publish_dt - now).total_seconds()
                    logger.debug(f"任务 {task['md_file']} 剩余时间: {remaining:.0f} 秒")
            
            # 移除已完成的任务
            for task in completed_tasks:
                self.tasks.remove(task)
            
            if not self.tasks:
                logger.info("所有任务已完成")
                break
            
            # 等待下次检查
            time.sleep(check_interval)
    
    def list_tasks(self):
        """列出所有待发表任务"""
        if not self.tasks:
            print("没有待发表任务")
            return
        
        print(f"\n当前有 {len(self.tasks)} 个待发表任务:\n")
        for i, task in enumerate(self.tasks, 1):
            print(f"{i}. {task['md_file']}")
            print(f"   发表时间: {task['publish_time']}")
            print(f"   风格: {task['style']}")
            print(f"   自动发表: {task['auto_publish']}")
            print()


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="定时发表微信公众号文章")
    parser.add_argument("--config", "-c", help="配置文件路径（JSON 格式）")
    parser.add_argument("--md-file", "-f", help="Markdown 文件路径")
    parser.add_argument("--publish-time", "-t", help="发表时间（格式：YYYY-MM-DD HH:MM:SS）")
    parser.add_argument("--style", "-s", default="academic_gray", help="HTML 风格")
    parser.add_argument("--list", "-l", action="store_true", help="列出所有任务")
    parser.add_argument("--check-interval", "-i", type=int, default=60, help="检查间隔（秒）")
    parser.add_argument("--auto-publish", action="store_true", help="自动发表（不推荐）")
    
    args = parser.parse_args()
    
    publisher = ScheduledPublisher(config_file=args.config)
    
    # 如果指定了配置文件，先加载
    if args.config:
        publisher.load_config(args.config)
    
    # 如果提供了单个任务参数
    if args.md_file and args.publish_time:
        publisher.add_task(
            md_file=args.md_file,
            publish_time=args.publish_time,
            style=args.style,
            auto_publish=args.auto_publish
        )
    
    # 列出任务
    if args.list:
        publisher.list_tasks()
        return
    
    # 运行定时器
    if publisher.tasks:
        try:
            publisher.run(check_interval=args.check_interval)
        except KeyboardInterrupt:
            logger.info("用户中断，退出定时发表器")
    else:
        logger.warning("没有待发表任务，退出")
        parser.print_help()


if __name__ == "__main__":
    main()

