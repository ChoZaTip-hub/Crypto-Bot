"""JSON serialization helpers."""

import json
from typing import Any


def dumps_json(data: Any) -> str:
    return json.dumps(data, default=str)


def loads_json(data: str) -> Any:
    return json.loads(data)
