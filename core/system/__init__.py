"""Central system lifecycle coordination and subsystem bootstrap.

Owns thread lifecycle, graceful shutdown, health monitoring, and
self-updating subsystem pipelines (SDE warehouse, ESI codegen).

Public API
----------
get_lifecycle()              — singleton SystemLifecycle accessor
register_thread(name, ...)   — register a managed thread
shutdown(timeout)            — graceful shutdown in reverse registration order
health_check()               — thread status report

bootstrap_all(settings)      — ensure SDE + ESI are ready at startup
ensure_sde_ready()           — SDE warehouse readiness check + optional update
ensure_esi_ready()           — ESI codegen readiness check + optional regenerate
prepare_sde_sources()        — ensure _sde/fsd exists (download if needed)
update_sde_full()            — full SDE pipeline incl. schema regen
update_esi_full(date)        — ESI spec fetch + full codegen regeneration
update_config()              — regenerate example.config.yaml
get_subsystem_status()       — read-only status dict for all subsystems
"""

from core.system.lifecycle import (
    SystemLifecycle,
    get_lifecycle,
)
from core.system.bootstrap import (
    bootstrap_all,
    ensure_sde_ready,
    ensure_esi_ready,
    prepare_sde_sources,
    update_sde_full,
    update_esi_full,
    update_config,
    get_subsystem_status,
)

__all__ = [
    "SystemLifecycle",
    "get_lifecycle",
    "bootstrap_all",
    "ensure_sde_ready",
    "ensure_esi_ready",
    "prepare_sde_sources",
    "update_sde_full",
    "update_esi_full",
    "update_config",
    "get_subsystem_status",
]
