"""过滤器测试"""
import pytest
from src.filters import CommandFilter

def test_block_sleep():
    filter = CommandFilter(enabled=True)
    should_block, reason = filter.should_block("sleep 10")
    assert should_block
    assert "Sleep" in reason

def test_block_python_c():
    filter = CommandFilter(enabled=True)
    should_block, reason = filter.should_block("python -c 'import os'")
    assert should_block
    assert "python -c" in reason.lower()

def test_allow_cat():
    filter = CommandFilter(enabled=True)
    should_block, reason = filter.should_block("cat file.py")
    assert not should_block
