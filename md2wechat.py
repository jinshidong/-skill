#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
命令行入口脚本
"""

import sys
from pathlib import Path

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from md2wechat import main

if __name__ == "__main__":
    main()
