#!/usr/bin/env python
"""
CalDAV MCP 서버 진입점
"""
import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.caldav_mcp import main

if __name__ == "__main__":
    main()
