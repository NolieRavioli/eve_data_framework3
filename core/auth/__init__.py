"""Authentication & authorization framework.

Handles: OAuth2 SSO, encrypted token storage, role-based access control,
client credential management, and access decorators.
"""

from core.auth.decorators import require_login, require_admin, require_role
from core.auth.tokens import pick_token, fresh_token, get_token, resolve_default_owner_id
from core.auth.identity import (
    link_public_user,
    list_public_users,
    count_public_owners,
    get_user_roles,
    grant_user_roles,
    revoke_user_role,
    list_all_user_roles,
    get_site_admin,
    upsert_site_admin,
    delete_site_admin,
)
from core.auth.credentials import CredentialManager

__all__ = [
    "require_login", "require_admin", "require_role",
    "pick_token", "fresh_token", "get_token", "resolve_default_owner_id",
    "link_public_user", "list_public_users", "count_public_owners",
    "get_user_roles", "grant_user_roles", "revoke_user_role", "list_all_user_roles",
    "get_site_admin", "upsert_site_admin", "delete_site_admin",
    "CredentialManager",
]
