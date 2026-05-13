"""Adapter package: YAML form-fill definitions + resolver + loader."""

from __future__ import annotations

from .loader import (
    Adapter,
    AdapterError,
    AdapterField,
    AdapterMatch,
    AdapterSubmit,
    list_bundled,
    list_user,
    load_adapter,
    load_all,
    match_url,
)
from .resolver import (
    FieldPlan,
    PlanEntry,
    ResolverError,
    SecretResolver,
    build_plan,
)

__all__ = [
    "Adapter",
    "AdapterError",
    "AdapterField",
    "AdapterMatch",
    "AdapterSubmit",
    "FieldPlan",
    "PlanEntry",
    "ResolverError",
    "SecretResolver",
    "build_plan",
    "list_bundled",
    "list_user",
    "load_adapter",
    "load_all",
    "match_url",
]
