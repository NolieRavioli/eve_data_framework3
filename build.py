"""build.py — Refresh the ESI spec and regenerate core/esi/generated/ and domain collectors.



Usage:

    python build.py              # fetch latest spec + regenerate generated + collectors

    python build.py --force      # force regenerate even if spec is current

    python build.py --spec-only  # only refresh the spec, skip codegen

    python build.py --gen-only   # only run core/esi/generated/ codegen, skip collectors

    python build.py --collectors # only regenerate domain collector packages

    python build.py --fullclean  # delete all data + generated files, then do a full build

"""



import argparse

import shutil

import sys

from pathlib import Path



from core.config import load_config, CONFIG_PATH


# Directories that are entirely auto-generated and safe to delete outright.
_GENERATED_PACKAGES = [
    "core/esi/generated",
    "core/esi/personal",
    "core/esi/corp",
    "core/esi/public",
]

# Individual data files / directories to remove (auth files are preserved).
_DATA_PATHS = [
    "_sde",
    "_privateData",
]


def _fullclean() -> None:
    """Delete all generated packages and data files."""
    # Remove auto-generated Python packages.
    for rel in _GENERATED_PACKAGES:
        target = Path(rel)
        if target.exists():
            shutil.rmtree(target)
            print(f"[fullclean] Removed {target}/")

    # Remove SDE YAML files and private data.
    for rel in _DATA_PATHS:
        target = Path(rel)
        if target.exists():
            shutil.rmtree(target)
            print(f"[fullclean] Removed {target}/")

    # Remove the DuckDB warehouse and ESI spec snapshots from _publicData/,
    # but preserve credentials (key, client_cred) if they exist.
    public_data = Path("_publicData")
    if public_data.exists():
        db_file = public_data / "public.duckdb"
        if db_file.exists():
            db_file.unlink()
            print(f"[fullclean] Removed {db_file}")
        esi_specs = public_data / "esi_specs"
        if esi_specs.exists():
            shutil.rmtree(esi_specs)
            print(f"[fullclean] Removed {esi_specs}/")

    # Remove all __pycache__ directories.
    for cache_dir in sorted(Path(".").rglob("__pycache__"), reverse=True):
        shutil.rmtree(cache_dir)
        print(f"[fullclean] Removed {cache_dir}/")

    print("[fullclean] Done.")





def main() -> None:

    parser = argparse.ArgumentParser(description="Refresh ESI spec and regenerate core/esi/generated/.")

    parser.add_argument("--force", action="store_true", help="Force codegen even if spec date matches.")

    parser.add_argument("--spec-only", action="store_true", help="Only refresh the spec; skip codegen.")

    parser.add_argument("--gen-only", action="store_true", help="Only run codegen from the cached spec; skip collectors.")

    parser.add_argument("--collectors", dest="collectors_only", action="store_true", help="Only regenerate domain collector packages.")

    parser.add_argument("--cache-only", dest="cache_only", action="store_true", help="Only regenerate core/esi/generated/cache_ddl.py.")

    parser.add_argument("--date", metavar="YYYY-MM-DD", help="Pin to a specific compatibility date.")

    parser.add_argument("--fullclean", action="store_true", help="Delete all data and generated files (including __pycache__), then exit.")

    args = parser.parse_args()



    # Load config so env vars (PUBLIC_DATA_FOLDER etc.) are set before anything touches paths.

    load_config(CONFIG_PATH)



    if args.fullclean:

        _fullclean()

        sys.exit(0)



    # --cache-only: only regenerate cache_ddl.py then exit.

    if args.cache_only:

        print("[build] Regenerating ESI cache schema (cache_ddl.py)\u2026")

        from utils.build.cache_codegen import generate_cache_schema

        result = generate_cache_schema(compatibility_date=args.date, force=True)

        print(

            f"[build] Cache schema done \u2014 date={result['compatibility_date']}"

            f"  routes={result['route_count']}"

            f"  columns={result['column_count']}"

        )

        print("[build] Done.")

        sys.exit(0)



    # Step 1: Spec fetch — skip if --gen-only or --collectors

    if not args.gen_only and not args.collectors_only:

        print("[build] Fetching ESI spec from CCP…")

        from core.esi.registry import refresh_esi_spec_registry

        status = refresh_esi_spec_registry(compatibility_date=args.date)

        print(

            f"[build] Spec ready  — date={status['compatibility_date']}"

            f"  routes={status.get('route_count', '?')}"

            f"  scopes={status.get('scope_count', '?')}"

            f"  schemas={status.get('schema_count', '?')}"

        )



    # Step 2: ESI cache schema — skip if --spec-only or --collectors

    if not args.spec_only and not args.collectors_only:

        print("[build] Generating ESI cache schema (cache_ddl.py)\u2026")

        from utils.build.cache_codegen import generate_cache_schema

        cache_result = generate_cache_schema(compatibility_date=args.date, force=args.force)

        _skipped = cache_result.get("skipped", False)

        print(

            f"[build] Cache schema {'skipped (up to date)' if _skipped else 'done'}"

            f" \u2014 date={cache_result['compatibility_date']}"

            f"  routes={cache_result['route_count']}"

            + (f"  columns={cache_result['column_count']}" if not _skipped else "")

        )



    # Step 3: core/esi/generated/ codegen — skip if --spec-only or --collectors

    if not args.spec_only and not args.collectors_only:

        print("[build] Regenerating core/esi/generated/…")

        from utils.build.esi_codegen import generate

        result = generate(compatibility_date=args.date, force=args.force)

        print(

            f"[build] Codegen done — date={result['compatibility_date']}"

            f"  ops={result['operation_count']}"

            f"  schemas={result['schema_count']}"

            f"  scopes={result['scope_count']}"

        )



    # Step 4: domain collector packages — skip if --spec-only or --gen-only

    if not args.spec_only and not args.gen_only:

        print("[build] Generating domain collector packages…")

        from utils.build.domain_codegen import generate_collectors

        result = generate_collectors(compatibility_date=args.date, force=args.force)

        print(

            f"[build] Collectors done — date={result['compatibility_date']}"

            f"  personal={result['personal_files']}"

            f"  corp={result['corp_files']}"

            f"  public={result['public_files']}"

        )



    print("[build] Done.")





if __name__ == "__main__":

    main()



