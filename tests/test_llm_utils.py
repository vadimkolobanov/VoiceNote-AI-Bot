import pytest

from src.services.llm import _parse_llm_json_response, UserIntent


def test_parse_llm_json_response_with_json_fence():
    resp = """```json
{
  "ok": true,
  "value": 123
}

