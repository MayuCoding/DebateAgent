import functools
from typing import Any, Callable, Dict

import logfire


def span(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attrs: Dict[str, Any] = kwargs.pop("span_attrs", {}) or {}
            with logfire.span(name, attributes=attrs):
                return func(*args, **kwargs)

        return wrapper

    return decorator
