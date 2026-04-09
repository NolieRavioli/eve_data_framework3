# Scheduler & Task Queue

EVE Data Framework runs background work through two complementary systems: the **task queue** (on-demand execution) and the **scheduler** (time-based execution). Both are visible and controllable from the Task Manager UI at `/tasks`.

---

## Task Queue

<!-- inject:task_queue -->

---

## Scheduler

<!-- inject:scheduler -->

---

## Default Scheduled Jobs

| Job ID | Label | Default Interval | Enabled |
|--------|-------|-----------------|---------|
| `market_refresh` | Market Data Refresh | 3600s (1 hour) | Yes |
| `structure_market_refresh` | Structure Market Orders Refresh | 3600s (1 hour) | Yes |
| `structure_discovery` | Structure Discovery | 86400s (24 hours) | Yes |
| `character_refresh` | Character Data Refresh | 86400s (24 hours) | Yes |
| `esi_spec_refresh` | ESI Spec + Codegen Refresh | 86400s (24 hours) | **No** |

Jobs can be enabled/disabled and their intervals adjusted through the Task Manager UI or the scheduler API.

---

## Adding a New Scheduled Job

<!-- inject:task_new_job -->

---

## Task Manager UI

The Task Manager at `/tasks` provides:

- **Queue tab** — view and cancel pending/running tasks, clear completed tasks
- **Scheduler tab** — view all registered jobs, toggle enabled, change intervals, trigger manual runs
- **ESI Rate Monitor** — real-time ESI rate limit and error budget display
- **API Explorer** — browse and test all registered ESI operations
