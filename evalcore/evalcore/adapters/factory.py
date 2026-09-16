"""Adapter factory: resolve an AdapterConfig to a concrete Target (TechDesign §2.2).

This is the single dispatch point that changes when a new adapter type is added — the
"second consumer" that justifies the Target abstraction.
"""

from evalcore.adapters.base import Target
from evalcore.adapters.http_adapter import HttpAdapter, N8nWebhookAdapter
from evalcore.adapters.python_adapter import PythonAdapter
from evalcore.config import (
    AdapterConfig,
    N8nWebhookAdapterConfig,
    PythonAdapterConfig,
)


def build_adapter(config: AdapterConfig) -> Target:
    # Check N8n before Http: N8nWebhookAdapterConfig is a subclass of HttpAdapterConfig.
    if isinstance(config, PythonAdapterConfig):
        return PythonAdapter(config.callable)
    if isinstance(config, N8nWebhookAdapterConfig):
        return N8nWebhookAdapter(config)
    return HttpAdapter(config)
