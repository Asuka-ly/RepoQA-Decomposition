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
    
    assert "sub_questions" in result
    assert len(result["sub_questions"]) == 1
    assert result["sub_questions"][0]["entry_candidates"][0] == "unknown"
    assert result["synthesis"] is not None


def test_normalize_result_from_legacy_aspects():
    decomposer = StrategicDecomposer(MagicMock())
    legacy = {
        "aspects": [
            {
                "description": "Investigate DefaultAgent call chain",
                "entry_point": "a.py::DefaultAgent.run",
                "symbols": ["DefaultAgent"],
                "priority": 1,
            }
        ]
    }
    normalized = decomposer._normalize_result(legacy, "How does it work?")
    assert "sub_questions" in normalized
    assert normalized["sub_questions"][0]["id"] == "SQ1"
    assert normalized["sub_questions"][0]["entry_candidates"][0] == "a.py::DefaultAgent.run"
    assert normalized["sub_questions"][0]["status"] == "open"
