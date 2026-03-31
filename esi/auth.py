"""Forwarding shim - real code lives in core.esi.auth."""
import importlib, sys
sys.modules[__name__] = importlib.import_module("core.esi.auth")
