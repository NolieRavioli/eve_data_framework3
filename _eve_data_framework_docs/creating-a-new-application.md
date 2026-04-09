# Creating a New Application

This guide walks through the full lifecycle of adding a new user-facing web tool to the EVE Data Framework.

---

## Overview

An **application** is a Flask blueprint packaged as a Python sub-package. The framework auto-discovers any package inside `applications/` that exposes a `Tool` attribute. Once discovered, the tool's blueprint is registered into the Flask app and its manifest entry appears in the sidebar.

Applications are purely UI — they render pages and return JSON. All heavy computation (ESI calls, DB writes) belongs in [collectors](collectors) or [analysis workers](analysis).

---

## Applications Layer

<!-- inject:applications -->

---

## Plugin Framework

<!-- inject:plugin_framework -->

---

## Step-by-Step: Creating a New Application

<!-- inject:task_new_application -->

---

## Design Patterns

### Triggering Collectors from Applications

Application worker files can import from `collectors.*` to trigger data collection:

```python
from applications._api import tasks
from collectors.my_domain.worker import fetch_data

task_id = tasks.enqueue("Refresh Data", fetch_data, queue="public")
```

### SSE Streaming

The task queue captures all `logging` calls from worker threads and streams them via Server-Sent Events. Use the `/tasks/api/stream/<task_id>` endpoint to connect:

```javascript
const source = new EventSource(`/tasks/api/stream/${taskId}`);
source.onmessage = (event) => {
    console.log(event.data);
};
```
