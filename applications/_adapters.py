"""Forwarding shim - real code lives in core.plugin.adapters."""
import importlib, sys
sys.modules[__name__] = importlib.import_module("core.plugin.adapters")
