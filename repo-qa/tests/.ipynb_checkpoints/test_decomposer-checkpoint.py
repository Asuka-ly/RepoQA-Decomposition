"""分解器测试"""
import pytest
from unittest.mock import MagicMock
from src.decomposer import StrategicDecomposer

def test_extract_symbols():
    decomposer = StrategicDecomposer(MagicMock())
    question = "How does DefaultAgent handle TimeoutError in LocalEnvironment?"
    symbols = decomposer._extract_symbols(question)
    
    assert "DefaultAgent" in symbols
    assert "LocalEnvironment" in symbols
    assert "TimeoutError" in symbols

def test_fallback_decomposition():
    decomposer = StrategicDecomposer(MagicMock())
    result = decomposer._create_fallback("Test question about code")
    
    assert "aspects" in result
    assert len(result["aspects"]) == 1
    assert result["aspects"][0]["entry_point"] == "unknown"
    assert result["synthesis"] is not None
