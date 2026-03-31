"""Forwarding shim — real code lives in esi/client/client.py until codegen is updated."""
# ruff: noqa: F401,F403
from esi.client.client import *
from esi.client.client import (
    execute_operation,
    fetch_all_pages,
    build_path,
    validate_write,
    MissingPathParam,
    OperationNotFound,
    AuthRequired,
)
