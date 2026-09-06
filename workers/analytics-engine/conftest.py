"""
Puts the analytics-engine root on sys.path so `from src.whitespace_radar import ...`
resolves under a bare `pytest` invocation, not only under `python -m pytest`.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
