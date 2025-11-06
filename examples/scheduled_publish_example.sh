#!/bin/bash
# 定时发布示例脚本
# 以 2023-01-01-neural-network-to-singularity.md 为例，设置晚上 20:30 定时发布

cd "$(dirname "$0")/.."

# 示例 1: 今天 20:30 定时发布
python publish_wechat.py \
    examples/2023-01-01-neural-network-to-singularity.md \
    --auto-publish \
    --scheduled-date "today" \
    --scheduled-time "20:30" \
    --style academic_gray

echo ""
echo "✅ 定时发布已设置！"
echo "   文章将在今天晚上 20:30 自动发布"
echo "   群发通知: 未启用（默认）"
echo ""
echo "其他示例："
echo "  # 明天 20:30 发布"
echo "  python publish_wechat.py article.md --auto-publish --scheduled-date tomorrow --scheduled-time 20:30"
echo ""
echo "  # 指定日期发布（如 2024-12-25 20:30）"
echo "  python publish_wechat.py article.md --auto-publish --scheduled-date 2024-12-25 --scheduled-time 20:30"

