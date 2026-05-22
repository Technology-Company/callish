"""callish — Django QuerySet façade for user-written API adapters."""

from __future__ import annotations

from .adapter import AdapterProtocol, BaseAdapter
from .exceptions import (
    AdapterError,
    AdapterValidationError,
    NotFound,
    RateLimited,
    Unauthorized,
    Upstream5xx,
)
from .forms import APIModelForm
from .manager import APIManager
from .models import APIModel
from .queryset import APIQuerySet

__version__ = "0.1.0"
default_app_config = "callish.apps.CallishConfig"

__all__ = [
    "AdapterError",
    "AdapterProtocol",
    "AdapterValidationError",
    "APIManager",
    "APIModel",
    "APIModelForm",
    "APIQuerySet",
    "BaseAdapter",
    "NotFound",
    "RateLimited",
    "Unauthorized",
    "Upstream5xx",
    "__version__",
]
