"""Tests for the adapter factory dispatch (no network)."""

from evalcore.adapters.factory import build_adapter
from evalcore.adapters.http_adapter import HttpAdapter, N8nWebhookAdapter
from evalcore.adapters.python_adapter import PythonAdapter
from evalcore.config import (
    HttpAdapterConfig,
    N8nWebhookAdapterConfig,
    PythonAdapterConfig,
)


def test_build_python_adapter() -> None:
    cfg = PythonAdapterConfig(type="python", callable="tests._fake_target:sync_dict")
    assert isinstance(build_adapter(cfg), PythonAdapter)


def test_build_http_adapter() -> None:
    cfg = HttpAdapterConfig(type="http", url="https://x.test/e", map={"answer": "$.answer"})
    adapter = build_adapter(cfg)
    assert isinstance(adapter, HttpAdapter)
    assert not isinstance(adapter, N8nWebhookAdapter)


def test_build_n8n_adapter() -> None:
    cfg = N8nWebhookAdapterConfig(type="n8n_webhook", url="https://x.test/webhook")
    assert isinstance(build_adapter(cfg), N8nWebhookAdapter)
