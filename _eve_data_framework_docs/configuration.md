# Configuration Reference

EVE Data Framework is configured through `config.yaml` at the repository root. This file is gitignored and must never be committed. Copy `example.config.yaml` as your starting point.

```bash
cp example.config.yaml config.yaml
```

The configuration is loaded once at startup by `core/config.py` and cached for the lifetime of the process.

---

## Configuration Overview

<!-- inject:configuration -->

---

## Configuration Reference

<!-- inject:readme_config_ref -->

---

## SDE

Controls which SDE datasets are loaded into the DuckDB warehouse at startup.

```yaml
SDE:
  agentsInSpace: false
  blueprints: false
  categories: true
  dogmaAttributes: false
  dogmaEffects: false
  factions: true
  groups: true
  mapConstellations: true
  mapRegions: true
  mapSolarSystems: true
  marketGroups: true
  metaGroups: true
  npcStations: true
  types: true
```

Each key corresponds to a JSONL file in `_sde/`. Set `true` to include the dataset; `false` to skip it (reduces startup time and memory usage).

---

## Structures

```yaml
Structures:
  error_cooldown_hours: 72       # How long to skip a structure after ESI returns an error
  forbidden_cooldown_hours: 168  # How long to skip after a 403 (no access)
```

These cooldowns prevent repeatedly hitting structures that consistently fail. Reset them by removing the cooldown timestamp from the `structures` table.

---

## Market

```yaml
Market:
  region_cooldown_minutes: 60    # Minimum wait between re-fetching a region's market orders
```

Prevents excessive API calls when regions are fetched frequently.
