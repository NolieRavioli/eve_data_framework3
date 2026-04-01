### 1. Naming: `characterDB_populateAll` / `populate_all`

`onboarding.py` → `populate.py`, main function `populate_all(owner_id)`. "Onboarding" implies a once-ever thing; this runs repeatedly as a refresh too. "Populate" says exactly what it does. Updating all references (__init__.py, auth callback, scheduler jobs catalog).

---

### 2. Who owns the table DDL for character data?

Here's the split that already exists and why:

| Table | Owners | Where DDL lives |
|---|---|---|
| `characters` (identity row — name, token, corp) | identity.py | **Core owns this.** It's auth infrastructure — the token can't even be fetched until the character row exists. `PrivateBase.metadata.create_all()` runs it. |
| `character_skills`, `character_assets`, `character_wallet` | **`collectors/character/populate.py`** | The collector owns these via `ensure_tables(engine)` using raw SQLite DDL — same pattern as DuckDB collectors, just against a SQLAlchemy engine connection instead of a DuckDB con. Runs at the top of each sub-fetcher. |

The SDE confusion you're sensing is real: SDE tables live in DuckDB and are owned by sde_loader.py — that's fine, `sde_loader` IS a collector. The `dim_types`, `dim_regions`, etc. tables have nothing to do with db. The only core-owned tables are identity tables (`users`, `site_admins`, `user_roles`, `characters`).

**Rule:** if a table exists purely to support authentication/identity → core owns it. If it contains fetched ESI data → the collector that fetches it owns it.

---

### 3. Move `*_generatedESI` → `core/esi/`; rename collectors → `analysis/`

The two-layer distinction that should exist but currently doesn't have a clear home:

| Layer | What it is | Where it should live |
|---|---|---|
| **ESI client** (raw operation executor + manifest) | `execute_operation`, `fetch_all_pages`, the manifest | `core/esi/generated/` (already correct) |
| **ESI domain wrappers** (typed per-endpoint functions, grouped by scope) | `personal_generatedESI/`, `corp_generatedESI/`, `public_generatedESI/` | `core/esi/personal/`, `core/esi/corp/`, `core/esi/public/` |
| **Analysis / data pipeline** | Market logic, structure discovery, character populate | `analysis/` (currently `collectors/`) |

**Why not `core/plugin/generated/`:** `core/plugin/` is the application framework — BaseTool, ToolManifest, ports, adapters, tool registry. It has nothing to do with ESI endpoints. Putting ESI domain wrappers there conflates the plugin system with ESI access. Someone looking for "how do I call the skills endpoint" would have to know to look inside the plugin system, which is wrong. Location should be determined by what the code *is* (typed ESI wrappers), not by who *consumes* it.

The generated domain wrappers call `core/esi/generated/client.py` — so they belong in `core/esi/` alongside the client they wrap. `analysis/` imports them from there. Once they move, `collectors/` is purely "logic that reads ESI and writes to DB" and the rename to `analysis/` becomes obvious.

---

## Updated Plan

**Phase A — Populate: rename + implement** *(depends on nothing)*

1. Rename onboarding.py → `populate.py`; rename `initialize_character` → `populate_all`
2. Update all references: __init__.py, auth.py (auth callback), jobs.py
3. Add `ensure_tables(engine)` in `populate.py` — creates `character_skills`, `character_wallet`, `character_assets` tables in private SQLite via raw DDL (not ORM models, since these are collector-owned, not identity)
4. Implement `_fetch_skills` — calls `core.esi.personal.skills.get_characters_character_id_skills`, upserts into `character_skills`
5. Implement `_fetch_wallet` — calls `core.esi.personal.wallet.get_characters_character_id_wallet`, upserts into `character_wallet`
6. Implement `_fetch_assets` — calls `core.esi.personal.assets.get_characters_character_id_assets` (paginated), upserts into `character_assets`

> **Note:** Phase A imports from `core.esi.personal.*` which won't exist until Phase B runs. Implement Phase A with the correct final import paths and do Phase B first, OR keep `*_generatedESI` imports during Phase A and update them as part of Phase B step 10.

**Phase B — Move generated ESI domain packages into esi** *(parallel with A)*

7. Update `codegen/domain_codegen.py`: change output paths `collectors/*_generatedESI/` → `core/esi/personal|corp|public/`; update the staleness-check to look in `core/esi/`; update init docstrings; the generated files themselves need no import-path changes (they only import `core.esi.generated.client`, which doesn't move)
8. Run `python build.py --collectors --force` — codegen creates `core/esi/personal/`, `core/esi/corp/`, `core/esi/public/` with all the same files in new locations
9. Update all imports in `analysis/character/populate.py` and any other analysis modules that imported from `*_generatedESI` → `core.esi.personal.*` etc.
10. Delete `collectors/personal_generatedESI/`, `collectors/corp_generatedESI/`, `collectors/public_generatedESI/` (now `analysis/` equivalents after Phase C rename)

**Phase C — Rename collectors → `analysis/`** *(depends on B)*

12. Rename directory collectors → `analysis/`
13. Update jobs.py — `from collectors.market` → `from analysis.market`, etc.
14. Update `codegen/domain_codegen.py` — remove any remaining collectors references
15. Update main.py if it imports `collectors.*`
16. Update AGENTS.md everywhere it says collectors — rewrite the layer table and directory map

**Relevant files**
- `collectors/character/onboarding.py` → `collectors/character/populate.py`
- `collectors/character/__init__.py` — update re-export (`populate_all`)
- `core/web/auth.py` — update enqueue call (`populate_all`)
- `core/scheduler/jobs.py` — update import + function name
- `codegen/domain_codegen.py` — update output paths (key file for Phase B)
- `core/esi/personal/`, `core/esi/corp/`, `core/esi/public/` — created by codegen in Phase B
- `collectors/personal_generatedESI/`, `collectors/corp_generatedESI/`, `collectors/public_generatedESI/` — deleted at end of Phase B (or end of Phase C after rename)
- `AGENTS.md` — rewrite layer table and directory map

**Verification**
1. `python build.py --collectors --force` completes without error; new files appear in `core/esi/personal/` etc.
2. `python -c "from core.esi.personal.skills import get_characters_character_id_skills; print('OK')"` passes
3. `python -c "from core.web import create_app; from config import get_runtime_settings; create_app(get_runtime_settings())"` starts cleanly
4. Log in with a character → `character_skills`, `character_wallet`, `character_assets` tables exist in private SQLite with real data

**Decisions**
- Character identity (`characters` table) stays in models — auth infrastructure
- Character data tables (`character_skills` etc.) owned by the collector via raw DDL `ensure_tables(engine)`
- Generated domain wrappers move to esi — they wrap the client, they're not analysis
- collectors → `analysis/` happens AFTER the generated packages are fully moved (Phase B must complete first)
- Phase A can be implemented immediately without waiting for B or C

---

Phase A can go now — it's self-contained and doesn't touch the package structure at all. Phases B+C are the bigger refactor. Want me to start with A, then tackle B+C?