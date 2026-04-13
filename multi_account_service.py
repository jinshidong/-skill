#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MD2WeChat 多公众号池后台服务入口。
"""

import sys
from pathlib import Path


SRC_ROOT = Path(__file__).parent / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from multi_account_service import main  # type: ignore  # noqa: E402


if __name__ == "__main__":
    main()
