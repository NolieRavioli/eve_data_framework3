"""Forwarding shim — real code lives in esi/client/ until codegen is updated."""
# ruff: noqa: F401,F403
from esi.client import *
from esi.client import COMPATIBILITY_DATE, OPERATION_COUNT, SCHEMA_COUNT, SCOPE_COUNT
