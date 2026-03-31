"""build.py — Refresh the ESI spec and regenerate esi/client/ and domain collectors.

Usage:
    python build.py              # fetch latest spec + regenerate generated + collectors
    python build.py --force      # force regenerate even if spec is current
    python build.py --spec-only  # only refresh the spec, skip codegen
    python build.py --gen-only   # only run esi/client/ codegen, skip collectors
    python build.py --collectors # only regenerate domain collector packages
"""

import argparse
import sys

from config import load_config, CONFIG_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh ESI spec and regenerate esi/client/.")
    parser.add_argument("--force", action="store_true", help="Force codegen even if spec date matches.")
    parser.add_argument("--spec-only", action="store_true", help="Only refresh the spec; skip codegen.")
    parser.add_argument("--gen-only", action="store_true", help="Only run codegen from the cached spec; skip collectors.")
    parser.add_argument("--collectors", dest="collectors_only", action="store_true", help="Only regenerate domain collector packages.")
    parser.add_argument("--date", metavar="YYYY-MM-DD", help="Pin to a specific compatibility date.")
    args = parser.parse_args()

    # Load config so env vars (PUBLIC_DATA_FOLDER etc.) are set before anything touches paths.
    load_config(CONFIG_PATH)

    # Step 1: Spec fetch — skip if --gen-only or --collectors
    if not args.gen_only and not args.collectors_only:
        print("[build] Fetching ESI spec from CCP…")
        from esi.spec_registry import refresh_esi_spec_registry
        status = refresh_esi_spec_registry(compatibility_date=args.date)
        print(
            f"[build] Spec ready  — date={status['compatibility_date']}"
            f"  routes={status.get('route_count', '?')}"
            f"  scopes={status.get('scope_count', '?')}"
            f"  schemas={status.get('schema_count', '?')}"
        )

    # Step 2: esi/client/ codegen — skip if --spec-only or --collectors
    if not args.spec_only and not args.collectors_only:
        print("[build] Regenerating esi/client/…")
        from codegen.esi_codegen import generate
        result = generate(compatibility_date=args.date, force=args.force)
        print(
            f"[build] Codegen done — date={result['compatibility_date']}"
            f"  ops={result['operation_count']}"
            f"  schemas={result['schema_count']}"
            f"  scopes={result['scope_count']}"
        )

    # Step 3: domain collector packages — skip if --spec-only or --gen-only
    if not args.spec_only and not args.gen_only:
        print("[build] Generating domain collector packages…")
        from codegen.domain_codegen import generate_collectors
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
