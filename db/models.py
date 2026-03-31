"""Forwarding shim — real code lives in core.db.models."""
import importlib, sys
sys.modules[__name__] = importlib.import_module("core.db.models")
