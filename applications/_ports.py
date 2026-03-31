"""Forwarding shim - real code lives in core.plugin.ports."""
import importlib, sys
sys.modules[__name__] = importlib.import_module("core.plugin.ports")
