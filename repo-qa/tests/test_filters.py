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
    assert "execute" in reason.lower()

def test_allow_cat():
    filter = CommandFilter(enabled=True)
    should_block, reason = filter.should_block("cat file.py")
    assert not should_block


def test_block_python_script_with_path():
    filter = CommandFilter(enabled=True)
    should_block, reason = filter.should_block("python tools/simulate_timeout.py")
    assert should_block
    assert "script" in reason.lower()


def test_block_heredoc_attempt():
    filter = CommandFilter(enabled=True)
    should_block, reason = filter.should_block("cat <<'EOF' > fake.txt")
    assert should_block
    assert any(k in reason.lower() for k in ["heredoc", "redirection"])
