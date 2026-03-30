"""util/collector_codegen.py
────────────────────────────
Generates typed ESI domain collector packages from the active manifest.

Writes three always-regenerated packages:
    esi/personal/    — character-scoped routes (character_id in path, or auth'd with fleet_id etc.)
    esi/corp/        — corporation-scoped routes (corporation_id in path, no character_id)
    esi/public/      — unauthenticated public routes (Alliance, Dogma, Universe, etc.)

Each package contains one module per ESI tag (e.g. assets.py, wallet.py).
Each module contains one typed wrapper function per operation in that tag.

Usage (via build.py):
    python build.py --collectors          # generate from active manifest
    python build.py --collectors --force  # regenerate even if already current
    python build.py                       # full pipeline: spec + generated + collectors
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Classification helpers
# ─────────────────────────────────────────────────────────────────────────────

def _classify_operation(op: dict) -> str:
    """
    Determine which package an operation belongs to.

    Rules (first match wins):
    1. Any path param named 'character_id'  → 'personal'
    2. Any path param named 'corporation_id' (no 'character_id') → 'corp'
    3. requires_auth=True but neither standard entity id → 'personal'
       (fleet commanders, alliance contacts, etc. still need a character token)
    4. requires_auth=False → 'public'
    """
    path_params = {p["name"] for p in op.get("parameters", []) if p.get("in") == "path"}
    if "character_id" in path_params:
        return "personal"
    if "corporation_id" in path_params:
        return "corp"
    if op.get("requires_auth"):
        return "personal"
    return "public"


def _tag_to_module(tag: str) -> str:
    """
    'Corporation Projects' → 'corporation_projects'
    'Planetary Interaction' → 'planetary_interaction'
    'User Interface' → 'user_interface'
    """
    return re.sub(r"[^a-zA-Z0-9]+", "_", tag).strip("_").lower()


def _op_to_fn(operation_id: str) -> str:
    """
    PascalCase → snake_case.
    'GetCharactersCharacterIdAssets' → 'get_characters_character_id_assets'
    """
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", operation_id).lower()


# ─────────────────────────────────────────────────────────────────────────────
# Code generators
# ─────────────────────────────────────────────────────────────────────────────

_PYTHON_BUILTINS = frozenset({
    "False", "None", "True", "and", "as", "assert", "async", "await",
    "break", "class", "continue", "def", "del", "elif", "else", "except",
    "finally", "for", "from", "global", "if", "import", "in", "is",
    "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try",
    "while", "with", "yield", "type", "id", "list", "dict", "str", "int",
    "float", "bool", "bytes", "set", "tuple", "range",
})


def _safe_param(name: str) -> str:
    """Suffix reserved words with underscore to avoid syntax errors."""
    return f"{name}_" if name in _PYTHON_BUILTINS else name


def _param_type(name: str) -> str:
    """Infer a sensible Python type annotation from the param name."""
    if name.endswith("_id") or name in ("page",):
        return "int"
    return "str"


def _render_function(op_id: str, op: dict) -> str:
    """Render a single typed wrapper function for one ESI operation."""
    fn_name = _op_to_fn(op_id)
    method = op.get("method", "GET")
    requires_auth = op.get("requires_auth", False)
    has_pages = op.get("pagination", {}).get("has_page_param", False)
    has_body = bool(op.get("request_body_schema_refs"))
    summary = op.get("summary", "").strip()
    scopes = op.get("scopes") or []
    cache_age = op.get("cache_age")

    # Collect path params (ordered as they appear in the parameter list)
    path_params: list[tuple[str, str]] = []
    for p in op.get("parameters", []):
        if p.get("in") == "path":
            raw = p["name"]
            path_params.append((_safe_param(raw), _param_type(raw)))

    # Build the Python signature
    sig_parts: list[str] = []
    for pname, ptype in path_params:
        sig_parts.append(f"{pname}: {ptype}")
    if requires_auth:
        sig_parts.append("token: str")
    if has_body:
        sig_parts.append("body: list | dict")

    # Return type annotation
    if method == "GET" and has_pages:
        ret_type = "list"
    elif method == "GET":
        ret_type = "dict | None"
    else:
        ret_type = "dict | None"

    sig = ", ".join(sig_parts)

    # Docstring
    doc_lines = [f'    """{summary}.']
    if scopes:
        doc_lines.append(f"    Scopes: {', '.join(scopes)}.")
    if cache_age:
        doc_lines.append(f"    Cache: {cache_age}s.")
    doc_lines.append('    """')
    docstring = "\n".join(doc_lines)

    # Build path_params dict literal
    if path_params:
        pp_items = ", ".join(
            f"{repr(p["name"])}: {_safe_param(p['name'])}"
            for p in op.get("parameters", [])
            if p.get("in") == "path"
        )
        pp_arg = f"path_params={{{pp_items}}}"
    else:
        pp_arg = "path_params=None"

    token_arg = "token=token" if requires_auth else "token=None"
    body_arg = "json_body=body" if has_body else ""

    # Function body
    if method == "GET" and has_pages:
        call_args = [f"    return fetch_all_pages(", f'        {repr(op_id)},', f"        {pp_arg},",
                     f"        {token_arg},", "    )"]
        body_code = "\n".join(call_args)
    elif method == "GET":
        exec_args = [repr(op_id), pp_arg, token_arg]
        exec_call = f"execute_operation({', '.join(exec_args)})"
        body_code = (
            f"    result = {exec_call}\n"
            f"    if result['status_code'] == 200:\n"
            f"        return result['body']\n"
            f"    logger.debug('%s returned %s for %s', {repr(op_id)}, result['status_code'], result['url'])\n"
            f"    return None"
        )
    else:
        exec_args = [repr(op_id), pp_arg, token_arg]
        if body_arg:
            exec_args.append(body_arg)
        exec_call = f"execute_operation({', '.join(exec_args)})"
        body_code = (
            f"    result = {exec_call}\n"
            f"    if result['status_code'] in (200, 201, 204):\n"
            f"        return result['body']\n"
            f"    logger.debug('%s returned %s for %s', {repr(op_id)}, result['status_code'], result['url'])\n"
            f"    return None"
        )

    return (
        f"\ndef {fn_name}({sig}) -> {ret_type}:\n"
        f"{docstring}\n"
        f"{body_code}\n"
    )


def _render_file(tag: str, ops: list[tuple[str, dict]], date: str, scope: str) -> str:
    """Render a complete module for one tag/scope combination."""
    lines: list[str] = []
    lines.append(f'"""')
    lines.append(f"esi/{scope}/{_tag_to_module(tag)}.py")
    lines.append(f"AUTO-GENERATED — do not edit by hand.")
    lines.append(f"Source: ESI {date}  |  Tag: {tag}  |  Scope: {scope}")
    lines.append(f"Regenerate: python build.py --collectors --force")
    lines.append(f'"""')
    lines.append("# ruff: noqa")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("import logging")
    lines.append("from typing import Any")
    lines.append("")
    lines.append("from esi.client.client import execute_operation, fetch_all_pages")
    lines.append("")
    lines.append("logger = logging.getLogger(__name__)")
    lines.append("")

    for op_id, op in ops:
        lines.append(_render_function(op_id, op))

    return "\n".join(lines)


def _render_init(date: str, scope: str) -> str:
    return (
        f'"""esi/{scope}/ — AUTO-GENERATED collector package. Do not edit.\n'
        f"Regenerate: python build.py --collectors --force\n"
        f'"""\n'
        f"# ruff: noqa\n"
        f"COLLECTOR_COMPATIBILITY_DATE: str = {repr(date)}\n"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Staleness check
# ─────────────────────────────────────────────────────────────────────────────

def collectors_are_current(date: str) -> bool:
    """Return True if all three collector packages match ``date``."""
    for scope in ("personal", "corp", "public"):
        init = Path(f"esi/{scope}/__init__.py")
        if not init.exists():
            return False
        if f"COLLECTOR_COMPATIBILITY_DATE: str = {repr(date)}" not in init.read_text(encoding="utf-8"):
            return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Main generator
# ─────────────────────────────────────────────────────────────────────────────

def generate_collectors(
    compatibility_date: str | None = None,
    force: bool = False,
) -> dict:
    """
    Read OPERATIONS / OPERATIONS_BY_TAG from esi.client.manifest and write
    the three domain collector packages.

    Parameters
    ----------
    compatibility_date:
        The ESI compatibility date to label the output. Defaults to
        ``esi.client.manifest.COMPATIBILITY_DATE``.
    force:
        If False (default), skip generation when all packages are already
        current.

    Returns
    -------
    dict with keys: compatibility_date, personal_files, corp_files,
    public_api_files, skipped.
    """
    from esi.client.manifest import OPERATIONS, OPERATIONS_BY_TAG, COMPATIBILITY_DATE as _MANIFEST_DATE
    date = compatibility_date or _MANIFEST_DATE

    if not force and collectors_are_current(date):
        print(
            f"[collector_codegen] esi/personal|corp|public/ already at {date} — nothing to do. "
            "Use force=True to regenerate."
        )
        return {"compatibility_date": date, "personal_files": 0, "corp_files": 0, "public_files": 0, "skipped": True}

    # Scope → tag → list of (op_id, op)
    buckets: dict[str, dict[str, list[tuple[str, dict]]]] = {
        "personal": {},
        "corp": {},
        "public": {},
    }

    for tag, op_ids in sorted(OPERATIONS_BY_TAG.items()):
        for op_id in op_ids:
            op = OPERATIONS[op_id]
            scope = _classify_operation(op)
            buckets[scope].setdefault(tag, []).append((op_id, op))

    counts: dict[str, int] = {"personal": 0, "corp": 0, "public": 0}

    for scope, tags in buckets.items():
        pkg_dir = Path(f"esi/{scope}")
        pkg_dir.mkdir(parents=True, exist_ok=True)
        (pkg_dir / "__init__.py").write_text(_render_init(date, scope), encoding="utf-8")

        for tag, ops in sorted(tags.items()):
            module_name = _tag_to_module(tag)
            content = _render_file(tag, ops, date, scope)
            (pkg_dir / f"{module_name}.py").write_text(content, encoding="utf-8")
            counts[scope] += 1

    print(
        f"[collector_codegen] Generated for {date} — "
        f"personal={counts['personal']} files, "
        f"corp={counts['corp']} files, "
        f"public={counts['public']} files."
    )
    return {
        "compatibility_date": date,
        "personal_files": counts["personal"],
        "corp_files": counts["corp"],
        "public_files": counts["public"],
        "skipped": False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _cli() -> None:
    parser = argparse.ArgumentParser(description="Generate esi/personal|corp|public/ from the active manifest.")
    parser.add_argument("--date", metavar="YYYY-MM-DD", help="Override compatibility date label")
    parser.add_argument("--force", action="store_true", help="Regenerate even if already current")
    args = parser.parse_args()

    from config import load_config, CONFIG_PATH
    load_config(CONFIG_PATH)

    result = generate_collectors(compatibility_date=args.date, force=args.force)
    print(f"Done: {result}")


if __name__ == "__main__":
    _cli()
