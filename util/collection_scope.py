import threading
from collections.abc import Callable
from typing import Any


_scope = threading.local()


def get_character_scope() -> set[int] | None:
    scoped = getattr(_scope, "character_ids", None)
    if not scoped:
        return None
    return set(scoped)


def set_character_scope(character_ids: set[int] | None) -> None:
    _scope.character_ids = set(character_ids) if character_ids else None


def clear_character_scope() -> None:
    _scope.character_ids = None


def run_with_character_scope(
    fn: Callable[..., Any],
    character_ids: set[int] | None,
    *args,
    **kwargs,
) -> Any:
    previous = get_character_scope()
    set_character_scope(character_ids)
    try:
        return fn(*args, **kwargs)
    finally:
        if previous:
            set_character_scope(previous)
        else:
            clear_character_scope()
