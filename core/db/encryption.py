"""At-rest encryption for database files and sensitive credentials.

Encrypts protected files when the application shuts down ("seal") and decrypts
them on startup ("unseal").  While the application is running, files remain in
plaintext on disk for normal DuckDB / SQLite access.

Master Key
----------
Set the ``EVE_MASTER_KEY`` environment variable to a hex-encoded 32-byte
(64 hex-character) random string.  When unset, encryption is disabled and
all seal/unseal operations are no-ops (backward compatible).

Generate a master key::

    python -c "import secrets; print(secrets.token_hex(32))"

**Do NOT put EVE_MASTER_KEY in config.yaml** — the config file sits alongside
the databases and would defeat the purpose.  Use your OS environment, a
systemd unit override, or a ``.env`` file **outside** the repository root.

Protected files
---------------
- ``_publicData/public.duckdb``  (+ ``.wal`` if present)
- ``_publicData/key``
- ``_publicData/secret``
- ``_publicData/client_cred``
- ``_privateData/<owner_id>/<owner_id>.db``  (all discovered SQLite files)

NOT protected: ``_sde/`` (public reference data, freely downloadable).
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

logger = logging.getLogger(__name__)

SEALED_SUFFIX = ".sealed"


# ── Key derivation ────────────────────────────────────────────────────────────


def _derive_fernet_key(master_hex: str) -> bytes:
    """Derive a Fernet-compatible key from a hex-encoded master secret via HKDF."""
    raw = bytes.fromhex(master_hex)
    derived = HKDF(
        algorithm=SHA256(),
        length=32,
        salt=None,
        info=b"eve-data-framework-at-rest-encryption",
    ).derive(raw)
    return base64.urlsafe_b64encode(derived)


def get_master_key() -> str | None:
    """Return the hex master key from ``EVE_MASTER_KEY``, or ``None`` if unset."""
    key = os.environ.get("EVE_MASTER_KEY", "").strip()
    return key if key else None


def is_encryption_enabled() -> bool:
    """Return True if at-rest encryption is configured."""
    return get_master_key() is not None


def _get_fernet() -> Fernet | None:
    master = get_master_key()
    if not master:
        return None
    return Fernet(_derive_fernet_key(master))


# ── File-level encrypt / decrypt ──────────────────────────────────────────────


def encrypt_file(src: Path) -> Path | None:
    """Encrypt *src* to ``<src>.sealed`` and remove the plaintext original.

    Returns the sealed path on success, or ``None`` if encryption is disabled
    or the source file does not exist.
    """
    fernet = _get_fernet()
    if fernet is None or not src.exists():
        return None

    sealed = Path(str(src) + SEALED_SUFFIX)
    data = src.read_bytes()
    sealed.write_bytes(fernet.encrypt(data))
    src.unlink()
    logger.debug("Sealed  %s", src)
    return sealed


def decrypt_file(sealed: Path) -> Path | None:
    """Decrypt ``<path>.sealed`` back to its original path and remove the sealed copy.

    Returns the plaintext path on success, or ``None`` on failure.
    """
    fernet = _get_fernet()
    if fernet is None or not sealed.exists():
        return None

    if not str(sealed).endswith(SEALED_SUFFIX):
        logger.warning("Not a sealed file: %s", sealed)
        return None

    original = Path(str(sealed)[: -len(SEALED_SUFFIX)])
    try:
        data = fernet.decrypt(sealed.read_bytes())
    except InvalidToken:
        logger.error(
            "Failed to decrypt %s — is EVE_MASTER_KEY correct?", sealed
        )
        raise SystemExit(
            f"At-rest decryption failed for {sealed}.  "
            "Check that EVE_MASTER_KEY matches the key used to seal the data."
        )

    original.write_bytes(data)
    sealed.unlink()
    logger.debug("Unsealed %s", original)
    return original


# ── Path helpers ──────────────────────────────────────────────────────────────


def _public_dir() -> Path:
    return Path(os.getenv("PUBLIC_DATA_FOLDER", "_publicData"))


def _private_dir() -> Path:
    return Path(os.getenv("EVE_PRIVATE_DATABASE_FOLDER", "_privateData"))


def _protected_public_files() -> list[Path]:
    """File paths in _publicData/ that should be sealed at rest."""
    pub = _public_dir()
    return [
        pub / "public.duckdb",
        pub / "public.duckdb.wal",
        pub / "key",
        pub / "secret",
        pub / "client_cred",
    ]


def _discover_private_dbs() -> list[Path]:
    root = _private_dir()
    if not root.exists():
        return []
    dbs: list[Path] = []
    for owner_dir in root.iterdir():
        if owner_dir.is_dir():
            dbs.extend(owner_dir.glob("*.db"))
    return dbs


def _discover_sealed_private_dbs() -> list[Path]:
    root = _private_dir()
    if not root.exists():
        return []
    sealed: list[Path] = []
    for owner_dir in root.iterdir():
        if owner_dir.is_dir():
            sealed.extend(owner_dir.glob(f"*{SEALED_SUFFIX}"))
    return sealed


# ── Bulk operations ───────────────────────────────────────────────────────────


def unseal_all() -> int:
    """Decrypt every protected file that has a ``.sealed`` counterpart.

    Called once at the very start of ``main.py``, **before** config init or
    any database access.  Returns the number of files successfully unsealed.
    """
    if not is_encryption_enabled():
        # Warn if sealed files exist but no key is configured.
        pub_sealed = [
            Path(str(p) + SEALED_SUFFIX)
            for p in _protected_public_files()
            if Path(str(p) + SEALED_SUFFIX).exists()
        ]
        priv_sealed = _discover_sealed_private_dbs()
        if pub_sealed or priv_sealed:
            logger.warning(
                "Found %d sealed file(s) but EVE_MASTER_KEY is not set — "
                "data cannot be unsealed.",
                len(pub_sealed) + len(priv_sealed),
            )
        return 0

    count = 0
    for path in _protected_public_files():
        sealed = Path(str(path) + SEALED_SUFFIX)
        if sealed.exists():
            if decrypt_file(sealed) is not None:
                count += 1

    for sealed in _discover_sealed_private_dbs():
        if decrypt_file(sealed) is not None:
            count += 1

    if count:
        logger.info("Unsealed %d protected file(s).", count)
    return count


def seal_all() -> int:
    """Encrypt every protected file and remove the plaintext copies.

    Called during graceful shutdown, **after** all database connections and
    writer threads are closed.  Returns the number of files sealed.
    """
    if not is_encryption_enabled():
        return 0

    count = 0
    for path in _protected_public_files():
        if path.exists():
            if encrypt_file(path) is not None:
                count += 1

    for db_path in _discover_private_dbs():
        if encrypt_file(db_path) is not None:
            count += 1

    if count:
        logger.info("Sealed %d protected file(s) for at-rest encryption.", count)
    return count
