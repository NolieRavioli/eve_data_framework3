#!/usr/bin/env python3
"""
sync_wiki.py --- Build and publish wiki pages from AGENTS.md + README.md + skeleton templates.

Pipeline:
1. Parse AGENTS.md --- extract all <!-- wiki:ID --> blocks into a dict
2. Parse README.md --- extract all <!-- wiki:ID --> blocks (readme_ prefixed) into the same dict
3. For each skeleton .md file in this directory:
   a. Replace <!-- inject:ID --> placeholders with extracted content
   b. Strip .md from inter-wiki links
   c. Remap AGENTS.md cross-section anchors to wiki page + anchor
3. Copy standalone .md files (no placeholders) as-is (with link rewriting)
4. Generate Home.md and _Sidebar.md
5. Commit and push to the wiki repo (or dry-run)

Usage:
    python sync_wiki.py                # clone wiki, sync, push
    python sync_wiki.py --dry-run      # process and show output, don't push
    python sync_wiki.py --no-push      # commit locally, don't push
    python sync_wiki.py --out DIR      # write processed files to DIR instead
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────────────────

DOCS_DIR = Path(__file__).parent          # _eve_data_framework_docs/
REPO_ROOT = DOCS_DIR.parent               # repository root
AGENTS_MD = REPO_ROOT / "AGENTS.md"
README_MD = REPO_ROOT / "README.md"
REMOTE_NAME = "origin"

EXCLUDE_FILES = {"sync_wiki.py", "__pycache__"}

GITHUB_REPO = "NolieRavioli/eve_data_framework3"

# Page order for the wiki sidebar
SIDEBAR_ORDER = [
    "Home",
    "installation",
    "usage",
    "architecture",
    "configuration",
    "authentication",
    "scheduler",
    "esi-client",
    "collectors",
    "analysis",
    "creating-a-new-application",
]

# Remap AGENTS.md cross-section anchors → wiki page + anchor.
# Only needed for anchor links that appear inside extracted wiki:ID blocks
# and point to sections that land on a different wiki page.
ANCHOR_REMAP = {
    "#repository-overview": "architecture#repository-overview",
    "#directory-map": "architecture#directory-map",
    "#layering-rules--import-discipline": "architecture#layering-rules--import-discipline",
    "#code-conventions": "architecture#code-conventions",
    "#database-architecture": "architecture#database-architecture",
    "#making-esi-requests": "esi-client#making-esi-requests",
    "#authentication--tokens": "authentication#eve-sso-tokens--roles",
    "#background-task-queue": "scheduler#task-queue",
    "#scheduler": "scheduler#scheduler",
    "#applications-layer": "creating-a-new-application#applications-layer",
    "#collectors-layer": "collectors#collector-reference",
    "#plugin-framework": "creating-a-new-application#plugin-framework",
    "#esi-client--code-generation": "esi-client#esi-client--code-generation",
    "#configuration": "configuration#configuration-overview",
    "#security-rules": "authentication#security-rules",
    "#creating-a-new-collector": "collectors#creating-a-new-collector",
    "#creating-a-new-application": "creating-a-new-application#step-by-step-creating-a-new-application",
    "#registering-a-new-scheduled-job": "scheduler#adding-a-new-scheduled-job",
}


# ── AGENTS.md Section Extractor ──────────────────────────────────────────────

def extract_wiki_sections(agents_path: Path) -> dict[str, str]:
    """
    Extract all <!-- wiki:ID --> ... <!-- /wiki:ID --> blocks from AGENTS.md.
    Returns a dict mapping section_id -> content (markers stripped).
    """
    text = agents_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r'<!-- wiki:(\w+) -->\n(.*?)<!-- /wiki:\1 -->',
        re.DOTALL,
    )
    sections = {}
    for m in pattern.finditer(text):
        sid = m.group(1)
        content = m.group(2).rstrip("\n")
        sections[sid] = content
    return sections


# ── Template Injection ───────────────────────────────────────────────────────

def inject_sections(template_text: str, sections: dict[str, str]) -> str:
    """Replace <!-- inject:ID --> placeholders with extracted AGENTS.md content."""
    def _replace(m):
        sid = m.group(1)
        if sid in sections:
            return sections[sid]
        return f"<!-- WARNING: section '{sid}' not found in source files -->"
    return re.sub(r'<!-- inject:(\w+) -->', _replace, template_text)


# ── Link Rewriting ───────────────────────────────────────────────────────────

def rewrite_links(text: str) -> str:
    """
    Rewrite markdown links for wiki context:
    1. Strip .md extension from inter-wiki links
    2. Remap AGENTS.md cross-section anchors to wiki page + anchor
    """
    # Strip .md from links: [text](page.md) → [text](page)
    #                        [text](page.md#anchor) → [text](page#anchor)
    text = re.sub(
        r'\]\(([a-zA-Z0-9_-]+)\.md(#[^)]+)?\)',
        lambda m: f']({m.group(1)}{m.group(2) or ""})',
        text,
    )

    # Remap cross-section anchors from AGENTS.md.
    # Sort by length (longest first) to prevent partial matches.
    for old_anchor, new_target in sorted(
        ANCHOR_REMAP.items(), key=lambda kv: len(kv[0]), reverse=True
    ):
        text = text.replace(f"]({old_anchor})", f"]({new_target})")

    return text


# ── File Processing ──────────────────────────────────────────────────────────

def process_files(sections: dict[str, str]) -> dict[str, str]:
    """
    Process all .md files in DOCS_DIR:
    - Inject AGENTS.md content into <!-- inject:... --> placeholders
    - Rewrite links for wiki context
    Returns a dict of filename -> processed content.
    """
    results = {}
    for md_file in sorted(DOCS_DIR.glob("*.md")):
        if md_file.name in EXCLUDE_FILES:
            continue
        raw = md_file.read_text(encoding="utf-8")
        processed = inject_sections(raw, sections)
        processed = rewrite_links(processed)
        results[md_file.name] = processed
    return results


def check_missing_sections(sections: dict[str, str]) -> set[str]:
    """Return set of placeholder IDs that have no matching source section."""
    placeholders = set()
    for md_file in DOCS_DIR.glob("*.md"):
        if md_file.name in EXCLUDE_FILES:
            continue
        for m in re.finditer(
            r'<!-- inject:(\w+) -->',
            md_file.read_text(encoding="utf-8"),
        ):
            placeholders.add(m.group(1))
    return placeholders - set(sections.keys())


# ── Sidebar & Home Generation ────────────────────────────────────────────────

def page_title(stem: str) -> str:
    """Convert a filename stem to a display title."""
    return stem.replace("-", " ").replace("_", " ").title()


def build_sidebar(page_stems: list[str]) -> str:
    """Generate _Sidebar.md with ordered wiki links."""
    stem_set = set(page_stems)
    ordered = [s for s in SIDEBAR_ORDER if s in stem_set]
    remaining = sorted(s for s in stem_set if s not in ordered and s != "Home")
    ordered.extend(remaining)

    lines = ["## EVE Data Framework Wiki\n"]
    for stem in ordered:
        title = page_title(stem)
        lines.append(f"* [[{title}|{stem}]]")
    return "\n".join(lines) + "\n"


def build_home() -> str:
    """Generate the Home.md landing page."""
    return """\
# EVE Data Framework

Welcome to the EVE Data Framework wiki.

## Getting Started

* [[Installation|installation]]
* [[Usage|usage]]

## Developer Guide

* [[Architecture|architecture]]
* [[Configuration|configuration]]
* [[Authentication|authentication]]
* [[Scheduler & Task Queue|scheduler]]
* [[ESI Client|esi-client]]
* [[Collectors|collectors]]
* [[Analysis Workers|analysis]]
* [[Creating A New Application|creating-a-new-application]]
"""


# ── Git Helpers ──────────────────────────────────────────────────────────────

def run_cmd(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a shell command, print it, and return the result."""
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=False)


def get_wiki_url() -> str:
    """Derive the wiki clone URL from the git remote."""
    result = subprocess.run(
        ["git", "remote", "get-url", REMOTE_NAME],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    url = result.stdout.strip()
    base = url[:-4] if url.endswith(".git") else url
    return base + ".wiki.git"


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Build and sync wiki from AGENTS.md + README.md + skeleton templates",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Process files and print output — don't touch the wiki repo",
    )
    parser.add_argument(
        "--no-push", action="store_true",
        help="Commit locally in temp dir but don't push",
    )
    parser.add_argument(
        "--out", type=Path, metavar="DIR",
        help="Write processed files to DIR instead of the wiki repo",
    )
    args = parser.parse_args()

    # ── Step 1: Parse source files ──
    if not AGENTS_MD.exists():
        print(f"[sync_wiki] ERROR: {AGENTS_MD} not found")
        sys.exit(1)

    print(f"[sync_wiki] Parsing {AGENTS_MD.name}...")
    sections = extract_wiki_sections(AGENTS_MD)
    print(f"  Extracted {len(sections)} section(s) from AGENTS.md")

    if README_MD.exists():
        print(f"[sync_wiki] Parsing {README_MD.name}...")
        readme_sections = extract_wiki_sections(README_MD)
        print(f"  Extracted {len(readme_sections)} section(s) from README.md")
        sections.update(readme_sections)
    else:
        print(f"[sync_wiki] WARNING: {README_MD} not found — skipping")

    print(f"  Total: {len(sections)} section(s): {', '.join(sorted(sections))}")

    # ── Step 2: Process skeleton files ──
    print("[sync_wiki] Processing template files...")
    pages = process_files(sections)
    print(f"  Processed {len(pages)} page(s)")

    # Warn about missing sections
    missing = check_missing_sections(sections)
    if missing:
        print(f"  WARNING: Missing AGENTS.md sections for: {', '.join(sorted(missing))}")

    # ── Dry-run ──
    if args.dry_run:
        print("\n" + "=" * 60)
        print("[sync_wiki] DRY RUN — Processed pages:")
        print("=" * 60)
        for name, content in sorted(pages.items()):
            header = f" {name} "
            print(f"\n{'-' * 30}{header}{'-' * max(1, 50 - len(header))}")
            print(content)
        sidebar = build_sidebar([Path(n).stem for n in pages])
        print(f"\n{'-' * 30} _Sidebar.md {'-' * 38}")
        print(sidebar)
        print(f"\n{'-' * 30} Home.md {'-' * 42}")
        print(build_home())
        return

    # ── Write to --out directory ──
    if args.out:
        out_dir = args.out
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, content in pages.items():
            (out_dir / name).write_text(content, encoding="utf-8")
        (out_dir / "Home.md").write_text(build_home(), encoding="utf-8")
        (out_dir / "_Sidebar.md").write_text(
            build_sidebar([Path(n).stem for n in pages]),
            encoding="utf-8",
        )
        print(f"[sync_wiki] Wrote {len(pages) + 2} files to {out_dir}")
        return

    # ── Clone wiki repo and sync ──
    try:
        wiki_url = get_wiki_url()
    except subprocess.CalledProcessError:
        print("[sync_wiki] ERROR: Could not determine git remote URL.")
        print("  Make sure you're in a git repo with a remote named 'origin'.")
        sys.exit(1)

    print(f"[sync_wiki] Wiki URL: {wiki_url}")

    with tempfile.TemporaryDirectory(prefix="eve_wiki_") as tmpdir:
        wiki_dir = Path(tmpdir) / "wiki"

        print("\n[sync_wiki] Cloning wiki repo...")
        result = subprocess.run(
            ["git", "clone", wiki_url, str(wiki_dir)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"[sync_wiki] Clone failed: {result.stderr.strip()}")
            print("  Initialize the wiki at github.com first.")
            sys.exit(1)

        # Write processed pages
        for name, content in pages.items():
            (wiki_dir / name).write_text(content, encoding="utf-8")

        # Generate Home.md and _Sidebar.md
        (wiki_dir / "Home.md").write_text(build_home(), encoding="utf-8")
        (wiki_dir / "_Sidebar.md").write_text(
            build_sidebar([Path(n).stem for n in pages]),
            encoding="utf-8",
        )

        # Check for changes
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=wiki_dir,
            capture_output=True,
            text=True,
        )
        if not status.stdout.strip():
            print("\n[sync_wiki] No changes — wiki is up to date.")
            return

        print(f"\n[sync_wiki] Changes:\n{status.stdout}")

        # Stage and commit
        run_cmd(["git", "add", "."], cwd=wiki_dir)
        run_cmd(
            ["git", "commit", "-m", "docs: sync wiki from AGENTS.md + README.md + templates"],
            cwd=wiki_dir,
        )

        if args.no_push:
            print("[sync_wiki] --no-push set; skipping push.")
            return

        # Push
        print("\n[sync_wiki] Pushing to wiki remote...")
        run_cmd(["git", "push", "origin", "master"], cwd=wiki_dir)
        print("[sync_wiki] Done!")


if __name__ == "__main__":
    main()
