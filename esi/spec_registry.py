"""Forwarding shim - real code lives in core.esi.registry."""
import importlib, sys
sys.modules[__name__] = importlib.import_module("core.esi.registry")
