import pytest

from src.services.llm import _parse_llm_json_response


# --- JSON with ```json ... ``` fence (with closing backticks) ---

def test_json_fence_with_json_label():
    resp = '```json\n{"key": "value", "num": 42}\n```'
    result = _parse_llm_json_response(resp)
    assert result == {"key": "value", "num": 42}


def test_json_fence_multiline():
    resp = """```json
{
  "ok": true,
  "value": 123
}
```"""
    result = _parse_llm_json_response(resp)
    assert result == {"ok": True, "value": 123}


# --- JSON with ``` ... ``` fence (no json label) ---

def test_fence_without_json_label():
    resp = '```\n{"status": "ok"}\n```'
    result = _parse_llm_json_response(resp)
    assert result == {"status": "ok"}


# --- Clean JSON without any fence ---

def test_clean_json_no_fence():
    resp = '{"a": 1, "b": 2}'
    result = _parse_llm_json_response(resp)
    assert result == {"a": 1, "b": 2}


def test_clean_json_multiline_no_fence():
    resp = '{\n  "hello": "world"\n}'
    result = _parse_llm_json_response(resp)
    assert result == {"hello": "world"}


# --- Invalid JSON returns dict with "error" key ---

def test_invalid_json_returns_error():
    resp = "this is not json at all"
    result = _parse_llm_json_response(resp)
    assert isinstance(result, dict)
    assert "error" in result


def test_malformed_json_returns_error():
    resp = '{"key": "value"'  # missing closing brace
    result = _parse_llm_json_response(resp)
    assert isinstance(result, dict)
    assert "error" in result


# --- JSON array wraps into {"results": data} ---

def test_json_array_returns_wrapped():
    resp = '[1, 2, 3]'
    result = _parse_llm_json_response(resp)
    assert isinstance(result, dict)
    assert result == {"results": [1, 2, 3]}


def test_json_array_in_fence_returns_wrapped():
    resp = '```json\n[{"a": 1}, {"b": 2}]\n```'
    result = _parse_llm_json_response(resp)
    assert isinstance(result, dict)
    assert result == {"results": [{"a": 1}, {"b": 2}]}


# --- Empty string returns dict with "error" key ---

def test_empty_string_returns_error():
    resp = ""
    result = _parse_llm_json_response(resp)
    assert isinstance(result, dict)
    assert "error" in result


def test_whitespace_only_returns_error():
    resp = "   \n\t  \n  "
    result = _parse_llm_json_response(resp)
    assert isinstance(result, dict)
    assert "error" in result


# --- JSON with trailing whitespace/newlines around fences ---

def test_fence_with_surrounding_whitespace():
    resp = '  \n```json\n{"trimmed": true}\n```\n  '
    result = _parse_llm_json_response(resp)
    assert result == {"trimmed": True}


# --- Unclosed fence (```json\n{...} without closing ```) ---

def test_unclosed_fence():
    resp = '```json\n{"unclosed": true}'
    result = _parse_llm_json_response(resp)
    assert result == {"unclosed": True}


# --- JSON with unicode characters ---

def test_unicode_values():
    resp = '{"message": "Привет мир", "emoji": "\\u2764"}'
    result = _parse_llm_json_response(resp)
    assert result == {"message": "Привет мир", "emoji": "\u2764"}


# --- Nested JSON objects ---

def test_nested_objects():
    resp = '```json\n{"outer": {"inner": {"deep": 1}}, "list": [1, 2]}\n```'
    result = _parse_llm_json_response(resp)
    assert result == {"outer": {"inner": {"deep": 1}}, "list": [1, 2]}


# --- JSON with extra text before/after fence ---

def test_extra_text_before_fence():
    resp = 'Here is the result:\n```json\n{"result": 42}\n```'
    result = _parse_llm_json_response(resp)
    assert result == {"result": 42}


def test_extra_text_after_fence():
    resp = '```json\n{"result": 42}\n```\nHope this helps!'
    result = _parse_llm_json_response(resp)
    assert result == {"result": 42}


def test_extra_text_before_and_after_fence():
    resp = 'Sure! Here you go:\n```json\n{"data": "ok"}\n```\nLet me know if you need more.'
    result = _parse_llm_json_response(resp)
    assert result == {"data": "ok"}
