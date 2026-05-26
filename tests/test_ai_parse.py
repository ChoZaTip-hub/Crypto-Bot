"""AI response parsing tests."""

import pytest

from app.services.ai.providers import parse_json_response


def test_parse_json_response_raw() -> None:
    data = parse_json_response('{"action": "BUY", "confidence": 0.7}')
    assert data["action"] == "BUY"


def test_parse_json_response_embedded() -> None:
    text = 'Here is result:\n{"action": "SELL", "confidence": 0.8}\n'
    data = parse_json_response(text)
    assert data["action"] == "SELL"


def test_parse_json_invalid() -> None:
    with pytest.raises(Exception):
        parse_json_response("not json")
