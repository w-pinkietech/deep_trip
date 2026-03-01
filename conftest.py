"""Root conftest: stub ten_runtime before any test collection."""
import sys
from unittest.mock import MagicMock

if "ten_runtime" not in sys.modules:
    _ten_runtime_mock = MagicMock()

    class _AsyncExtension:
        def __init__(self, name: str) -> None:
            self.name = name

    _ten_runtime_mock.AsyncExtension = _AsyncExtension
    _ten_runtime_mock.StatusCode.OK = 0
    sys.modules["ten_runtime"] = _ten_runtime_mock
