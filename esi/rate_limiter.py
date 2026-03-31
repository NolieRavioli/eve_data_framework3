"""Forwarding shim - real code lives in core.queue.esi_req."""
import importlib, sys
sys.modules[__name__] = importlib.import_module("core.queue.esi_req")
