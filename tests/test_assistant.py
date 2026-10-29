import os
from unittest.mock import Mock

from scout import assistant


def test_empty_question():
    result = assistant.answer_question("  ", {}, [])
    assert result["mode"] == "local"
    assert result["sources"] == []
    assert "Enter a question" in result["answer"]


def test_no_api_key_uses_local_fallback(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = assistant.answer_question(
        "What documents should I prepare?",
        {},
        [{"name": "Example scholarship", "documents": "Income certificate"}],
    )
    assert result["mode"] == "local"
    assert "Income certificate" in result["answer"]


def test_extract_text_skips_non_text_parts():
    payload = {
        "candidates": [{
            "content": {"parts": [{"thoughtSignature": "abc"}, {"text": "  Hello  "}]}
        }]
    }
    assert assistant._extract_text(payload) == "Hello"


def test_successful_gemini_response(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test")
    mock_response = Mock()
    mock_response.ok = True
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "Answer grounded in sources."}]}}]
    }
    monkeypatch.setattr(assistant.requests, "post", lambda *args, **kwargs: mock_response)
    result = assistant.answer_question(
        "What documents should I prepare?",
        {},
        [{"name": "Example scholarship", "documents": "Income certificate"}],
    )
    assert result["mode"] == "gemini"
    assert result["answer"] == "Answer grounded in sources."


def test_empty_gemini_response_falls_back(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    mock_response = Mock()
    mock_response.ok = True
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"thoughtSignature": "abc"}]}, "finishReason": "STOP"}]
    }
    monkeypatch.setattr(assistant.requests, "post", lambda *args, **kwargs: mock_response)
    result = assistant.answer_question(
        "What documents should I prepare?",
        {},
        [{"name": "Example scholarship", "documents": "Income certificate"}],
    )
    assert result["mode"] == "local"
    assert "no readable answer" in result["answer"]


def test_http_error_falls_back(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    mock_response = Mock()
    mock_response.ok = False
    mock_response.status_code = 429
    monkeypatch.setattr(assistant.requests, "post", lambda *args, **kwargs: mock_response)
    result = assistant.answer_question(
        "What documents should I prepare?",
        {},
        [{"name": "Example scholarship", "documents": "Income certificate"}],
    )
    assert result["mode"] == "local"
    assert "HTTP 429" in result["answer"]
