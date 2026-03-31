"""Forwarding shim - real code lives in core.db.publicDB."""
import importlib, sys
sys.modules[__name__] = importlib.import_module("core.db.publicDB")
