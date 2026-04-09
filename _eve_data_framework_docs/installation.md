# Installation

This guide walks through setting up EVE Data Framework from scratch on a fresh machine.

---

<!-- inject:readme_install -->

> **Tip:** It is recommended to use a virtual environment:
> ```bash
> python3 -m venv venv
> source venv/bin/activate        # Linux/macOS
> # or: venv\Scripts\activate     # Windows
> pip install -r requirements.txt
> ```
>
> Set `auto_install: true` in `config.yaml` to have the application install missing packages automatically on each startup.

**Minimum config values to review before first run:**

| Key | Location | Notes |
|-----|----------|-------|
| `host` | `Runtime.host` | `127.0.0.1` for local only; `0.0.0.0` to allow network access |
| `port` | `Runtime.port` | Default `5000` |
| `secret_key` | `Runtime.secret_key` | Set a long random string for persistent sessions |

---

## Register an EVE Developer Application

1. Go to [https://developers.eveonline.com/applications](https://developers.eveonline.com/applications) and create a new application.
2. Set the **Connection Type** to `Authentication & API Access`.
3. Set the **Callback URL** to `http://127.0.0.1:5000/callback` (adjust port if needed).
4. Add whatever ESI scopes your use case requires. The framework defaults to requesting all available scopes — you can narrow this down after setup.
5. Note your **Client ID** and **Client Secret**.

---

## First-Run Setup

<!-- inject:readme_first_run -->

### Detailed OAuth Setup

When the **Setup Wizard** loads:

1. Enter your **Client ID**, **Client Secret**, and **Callback URL** from the developer application registration step.
2. The **Scopes** field accepts a JSON array, space-separated, or comma-separated list. Leave it blank to default to all available scopes.
3. Click Save.

### Log In as Site Owner

After saving credentials, you will be redirected to `/setup/owner`. Click **Login with EVE Online**.

- Complete the EVE SSO flow in the browser.
- The first account to log in becomes the **site owner** — this account has full unconditional access and cannot be deleted by other admins.
- Subsequent logins create regular user accounts and are automatically granted the roles listed in `config.yaml` under `Auth.default_roles`.

### Verify

After logging in you should see your character card on the **Dashboard** (`/dashboard`). The task queue will begin processing the initial character data collection in the background.

Check the **System** page (`/system`) to confirm all subsystems are healthy:
- `SDE` — green if the SDE warehouse loaded correctly
- `ESI` — green if the OpenAPI spec was fetched and codegen ran
- `Database` — green if DuckDB is writable

---

## Directory Structure After First Run

```
_publicData/
  public.duckdb       # DuckDB warehouse (market orders, SDE, structures, auth)
  client_cred         # Fernet-encrypted OAuth credentials
  key                 # Fernet key — back this up, losing it requires re-authentication

_esi_specs/           # Cached ESI OpenAPI spec snapshots

_privateData/
  {owner_id}/
    {owner_id}.db     # Per-character SQLite (skills, wallet, assets, tokens)

_sde/                 # Downloaded SDE JSONL files
```

> **Security:** Never commit `config.yaml`, `_publicData/key`, `_publicData/client_cred`, or `_privateData/` to version control. All are gitignored by default.

---

## Updating

```bash
git pull
pip install -r requirements.txt
python3 main.py
```

Or use the in-app **System Update** button at `/system` which runs the same steps and restarts the process automatically.
