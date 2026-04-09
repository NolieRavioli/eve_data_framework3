# Authentication & User Management

EVE Data Framework uses EVE Online's official SSO (Single Sign-On) for authentication. No passwords are stored — all identity is delegated to CCP's OAuth2 server.

---

## How Authentication Works

Every user authenticates through EVE Online. When a user logs in:

1. They are redirected to `login.eveonline.com` to authorize the app
2. CCP validates their EVE credentials
3. CCP redirects back to the framework with an authorization code
4. The framework exchanges the code for access + refresh tokens
5. Tokens are encrypted (Fernet) and stored in the character's private SQLite database
6. A session is issued identifying the user by their `owner_id`

There are no local username/password accounts.

---

## EVE SSO, Tokens & Roles

<!-- inject:auth -->

---

## Managing Users

After first login, user management is handled through the **Admin Panel** (`/admin`):

- **Grant roles** — select a user and add role names
- **Revoke roles** — remove specific roles from a user
- **Promote to admin** — grant site admin status
- **Delete users** — remove a user entirely

The site owner is established on first login and cannot be deleted.

---

## Adding Characters

Each user can link multiple EVE characters to their account:

1. Click **Add Character** from the sidebar
2. Authorize the new character through EVE SSO
3. The character is linked to your existing `owner_id`

Switching characters is instant — use the character selector in the sidebar.

---

## Security Rules

<!-- inject:security -->

### Security Notes

<!-- inject:readme_security_notes -->
