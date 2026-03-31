"""Forwarding shim - real code lives in core.queue (scheduler + streams)."""
import importlib, sys
sys.modules[__name__] = importlib.import_module("core.queue")
