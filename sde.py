"""Forwarding shim - real code lives in core.sde."""
import importlib, sys
sys.modules[__name__] = importlib.import_module("core.sde")
