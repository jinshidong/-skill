#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信公众号发表命令行工具

将 Markdown 文件转换为 HTML 并发表到微信公众号。
"""

import sys
import argparse
import re
from pathlib import Path

# 添加 src 目录到路径
src_path = str(Path(__file__).parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from wechat_publisher import publish_from_markdown, WeChatPublisher  # type: ignore


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="发表 Markdown 文章到微信公众号",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本发表（需要手动确认）
  python publish_wechat.py article.md

  # 指定风格
  python publish_wechat.py article.md --style festival

  # 使用无头模式（不推荐，不利于调试）
  python publish_wechat.py article.md --headless

  # 仅插入内容，不清空编辑器
  python publish_wechat.py article.md --no-clear

  # 交互模式：打开浏览器后手动操作
  python publish_wechat.py --interactive
        """
    )
    
    parser.add_argument(
        "md_file",
        nargs="?",
        help="Markdown 文件路径"
    )
    parser.add_argument(
        "--style", "-s",
        default="academic_gray",
        choices=["academic_gray", "festival", "tech", "announcement"],
        help="HTML 风格（默认: academic_gray）"
    )
    parser.add_argument(
        "--user-data-dir", "-d",
        default="./tmp_profile",
        help="浏览器用户数据目录（用于持久化登录态，默认: ./tmp_profile）"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="使用无头模式（不显示浏览器窗口）"
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="不清空编辑器，在现有内容后追加"
    )
    parser.add_argument(
        "--auto-publish",
        action="store_true",
        help="自动发表（不推荐，存在风险）"
    )
    parser.add_argument(
        "--scheduled-time",
        type=str,
        help="定时发表时间，格式 HH:MM，如 20:30（需要配合 --auto-publish 使用）"
    )
    parser.add_argument(
        "--scheduled-date",
        type=str,
        help="定时发表日期，格式 YYYY-MM-DD 或 today 或 tomorrow，如 2024-12-25。默认为 today"
    )
    parser.add_argument(
        "--enable-group-notify",
        action="store_true",
        help="启用群发通知（默认不启用）"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="交互模式：仅打开浏览器，不插入内容"
    )
    
    args = parser.parse_args()
    
    # 交互模式
    if args.interactive:
        print("=" * 60)
        print("交互模式：登录设置")
        print("=" * 60)
        print("\n📋 操作步骤：")
        print("1. 浏览器会自动打开微信公众号登录页面")
        print("2. 请在浏览器中完成登录（扫码或账号密码）")
        print("3. 登录成功后，脚本会自动检测并保存登录态")
        print("4. 如果已登录，按 Ctrl+C 可随时退出")
        print("\n" + "=" * 60 + "\n")
        
        publisher = WeChatPublisher(
            user_data_dir=args.user_data_dir,
            headless=args.headless
        )
        
        try:
            # 交互模式下先导航到主页，便于检测登录状态
            if not publisher.start_browser(go_to_home=True):
                print("❌ 启动浏览器失败")
                return 1
            
            print("✅ 浏览器已打开")
            
            # 检查是否已登录
            if publisher.check_login():
                print("✅ 检测到已登录状态，登录态已保存")
                print("\n💡 提示：您可以继续使用浏览器，或按 Enter 键关闭浏览器")
                input()
            else:
                print("\n⏳ 等待您登录...")
                print("   请在浏览器中完成登录操作")
                
                # 等待登录
                if publisher.wait_for_login(timeout=300):
                    print("\n✅ 登录成功！登录态已保存到:", args.user_data_dir)
                    print("\n💡 提示：您可以继续使用浏览器，或按 Enter 键关闭浏览器")
                    input()
                else:
                    print("\n⚠️  登录超时或未检测到登录状态")
                    print("   请检查：")
                    print("   1. 是否已完成登录")
                    print("   2. 是否在正确的页面")
                    print("   3. 网络连接是否正常")
                    print("\n   按 Enter 键关闭浏览器（即使未登录也会保存当前状态）")
                    input()
            
        except KeyboardInterrupt:
            print("\n\n⚠️  用户中断，正在关闭浏览器...")
        finally:
            publisher.close()
            print("\n✅ 浏览器已关闭")
        
        return 0
    
    # 检查文件参数
    if not args.md_file:
        parser.error("请提供 Markdown 文件路径，或使用 --interactive 进入交互模式")
    
    md_file = Path(args.md_file)
    if not md_file.exists():
        print(f"错误: 文件不存在: {md_file}")
        return 1
    
    # 发表
    print(f"正在发表: {md_file}")
    print(f"风格: {args.style}")
    print(f"用户数据目录: {args.user_data_dir}")
    print()
    
    # 验证定时时间格式
    scheduled_time = None
    scheduled_date = None
    if args.scheduled_time:
        if not re.match(r'^\d{2}:\d{2}$', args.scheduled_time):
            print(f"错误: 定时时间格式不正确，应为 HH:MM，如 20:30")
            return 1
        scheduled_time = args.scheduled_time
        if not args.auto_publish:
            print("提示: 使用 --scheduled-time 时建议配合 --auto-publish 使用")
    
    # 验证定时日期格式
    if args.scheduled_date:
        # 支持 today、tomorrow 或 YYYY-MM-DD 格式
        if args.scheduled_date.lower() in ['today', 'tomorrow', '今天', '明天']:
            scheduled_date = args.scheduled_date.lower()
            if scheduled_date in ['今天']:
                scheduled_date = 'today'
            elif scheduled_date in ['明天']:
                scheduled_date = 'tomorrow'
        elif re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', args.scheduled_date):
            # 验证日期是否有效
            try:
                from datetime import datetime
                datetime.strptime(args.scheduled_date, '%Y-%m-%d')
                scheduled_date = args.scheduled_date
            except ValueError:
                print(f"错误: 日期格式不正确或无效，应为 YYYY-MM-DD，如 2024-12-25")
                return 1
        else:
            print(f"错误: 日期格式不正确，应为 YYYY-MM-DD、today 或 tomorrow，如 2024-12-25")
            return 1
    
    result = publish_from_markdown(
        md_file=str(md_file),
        user_data_dir=args.user_data_dir,
        style=args.style,
        headless=args.headless,
        clear_editor=not args.no_clear,
        auto_publish=args.auto_publish,
        scheduled_time=scheduled_time,
        scheduled_date=scheduled_date,
        enable_group_notify=args.enable_group_notify
    )
    
    if result.get("ok"):
        print("\n✅ 发表成功！")
        if result.get("content_length"):
            print(f"   编辑器内容长度: {result['content_length']} 字符")
        if result.get("publish"):
            publish_info = result['publish']
            print(f"   发表状态: {publish_info.get('message', '未知')}")
            if publish_info.get("scheduled_time"):
                date_str = publish_info.get("scheduled_date", "today")
                if date_str == "today":
                    date_str = "今天"
                elif date_str == "tomorrow":
                    date_str = "明天"
                print(f"   定时发表时间: {date_str} {publish_info['scheduled_time']}")
        return 0
    else:
        print(f"\n❌ 发表失败: {result.get('error', '未知错误')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

