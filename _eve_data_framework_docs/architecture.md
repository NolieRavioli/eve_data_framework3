# Architecture Overview

EVE Data Framework is a self-hosted Flask web application for interacting with the EVE Online ESI REST API. It is structured into clean architectural layers with strict import discipline.

---

## High-Level Layers

```
┌─────────────────────────────────────────────────────────────┐
│                      applications/                          │
│  User-facing web tools (Dashboard, Market Browser, etc.)   │
│  Imports only from: applications._api                       │
├─────────────────────────────────────────────────────────────┤
│                       collectors/                           │
│  ESI data fetching & persistence                            │
│  Imports only: core.*                                       │
├─────────────────────────────────────────────────────────────┤
│                         core/                                │
│  Infrastructure: DB, ESI, auth, tasks, scheduler, bus       │
│  No imports from applications/ or collectors/               │
└─────────────────────────────────────────────────────────────┘
```

---

## Startup Sequence (`main.py`)

The application initializes in strict order:

1. **Decrypt at-rest data** — Fernet-sealed credentials and databases are unsealed
2. **Load config** — `core/config.py` reads `config.yaml` once, caches forever
3. **Start event bus** — `core/bus` routing for logs and live data
4. **Register lifecycle coordinator** — `core/system/lifecycle.py` tracks all managed threads
5. **Start DB writer thread** — serializes all DuckDB writes
6. **Initialize public DB schema** — idempotent DDL for core tables
7. **Bootstrap** — ensure ESI spec is current, SDE warehouse is built
8. **Warm SDE caches** — load SDE into memory (types, regions, systems, etc.)
9. **Initialize collector tables** — call each collector's `ensure_tables()`
10. **Start scheduler** — background job runner starts ticking every 30 seconds
11. **Start Flask** — HTTP server begins accepting connections

---

## Repository Overview

<!-- inject:overview -->

---

## Directory Map

<!-- inject:directory_map -->

---

## Layering Rules & Import Discipline

<!-- inject:layering_rules -->

---

## Code Conventions

<!-- inject:code_conventions -->

---

## Database Architecture

<!-- inject:database -->
