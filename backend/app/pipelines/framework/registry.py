"""Pipeline registry: name → entry point. The worker and the CLI use the same entry points (DDR-63)."""

from __future__ import annotations

from collections.abc import Callable

from app.pipelines.framework.context import RunContext

PipelineFn = Callable[[RunContext], None]
_REGISTRY: dict[str, PipelineFn] = {}


def register(name: str) -> Callable[[PipelineFn], PipelineFn]:
    def decorator(fn: PipelineFn) -> PipelineFn:
        if name in _REGISTRY:
            raise ValueError(f"pipeline {name} registered twice")
        _REGISTRY[name] = fn
        return fn

    return decorator


def get(name: str) -> PipelineFn:
    load_all()
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError(f"pipeline {name} has no implementation yet") from None


def implemented() -> frozenset[str]:
    load_all()
    return frozenset(_REGISTRY)


def load_all() -> None:
    """Import every pipeline package so its @register decorators run. Later tasks add P2, P3, K1–K3."""
    from app.pipelines.p1_sop import pipeline as _p1  # noqa: F401
    from app.pipelines.p2_elt import pipeline as _p2  # noqa: F401
