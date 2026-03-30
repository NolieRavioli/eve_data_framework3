"""SDE bootstrap: download, unzip, language-prune, rebuild DuckDB warehouse."""
import logging
import os
import shutil
import sys
import time
import zipfile
from pathlib import Path

import requests
import yaml

from esi.spec_registry import refresh_esi_spec_registry
from db.sde import refresh_all_caches
from build import sde_loader
from db import sde_store

logger = logging.getLogger(__name__)

SDE_URL = "https://eve-static-data-export.s3-eu-west-1.amazonaws.com/tranquility/sde.zip"
SDE_PATH = Path(os.getenv("SDE_PATH", "_sde"))
SDE_ZIP_PATH = Path("_sde_tmp.zip")

FIELDS_TO_CLEAN = [
    "name",
    "description",
    "shortDescription",
    "descriptionID",
    "nameID",
    "displayNameID",
    "tooltipDescriptionID",
    "leaderTypeNameID",
    "serviceNameID",
    "operationNameID",
]

_LAST_PROGRESS_LENGTH = 0


def _progress_print(message: str, *, final: bool = False) -> None:
    global _LAST_PROGRESS_LENGTH
    text = str(message)
    padding = " " * max(0, _LAST_PROGRESS_LENGTH - len(text))
    sys.stdout.write(f"\r{text}{padding}")
    if final:
        sys.stdout.write("\n")
        _LAST_PROGRESS_LENGTH = 0
    else:
        _LAST_PROGRESS_LENGTH = len(text)
    sys.stdout.flush()


def _supported_languages() -> list[str]:
    raw = os.getenv("SUPPORTED_LANGUAGES", "en")
    return [item.strip() for item in raw.split(",") if item.strip()]


def download_sde(url: str = SDE_URL, dest: Path = SDE_ZIP_PATH, retries: int = 3) -> dict:
    backoff = 2
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            logger.info("Downloading SDE (attempt %s)...", attempt)
            _progress_print(f"[SDE] downloading archive (attempt {attempt})")
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()
            with dest.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=8192):
                    handle.write(chunk)
            logger.info("SDE download complete.")
            _progress_print("[SDE] download complete", final=True)
            return {
                "etag": response.headers.get("ETag"),
                "last_modified": response.headers.get("Last-Modified"),
                "sha256": sde_store.compute_file_sha256(dest),
                "zip_path": str(dest),
            }
        except requests.RequestException as exc:
            last_error = exc
            logger.warning("SDE download attempt %s failed: %s", attempt, exc)
            if attempt < retries:
                time.sleep(backoff)
                backoff *= 2
    raise RuntimeError(f"Failed to download SDE after {retries} attempts: {last_error}")


def unzip_sde(zip_path: Path = SDE_ZIP_PATH, extract_to: Path = SDE_PATH) -> None:
    if extract_to.exists():
        logger.info("Cleaning existing SDE folder at %s", extract_to)
        shutil.rmtree(extract_to)
    extract_to.mkdir(parents=True, exist_ok=True)
    logger.info("Extracting %s to %s", zip_path, extract_to)
    _progress_print(f"[SDE] extracting archive to {extract_to}")
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(extract_to)
    logger.info("SDE extraction complete.")
    _progress_print("[SDE] extraction complete", final=True)


def cleanup(zip_path: Path = SDE_ZIP_PATH) -> None:
    if zip_path.exists():
        zip_path.unlink()
        logger.info("Removed temporary SDE archive %s", zip_path)


def clean_multilang_fields(data):
    supported_languages = _supported_languages()
    if isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            if key in FIELDS_TO_CLEAN and isinstance(value, dict):
                cleaned[key] = {lang: value[lang] for lang in supported_languages if lang in value}
            else:
                cleaned[key] = clean_multilang_fields(value)
        return cleaned
    if isinstance(data, list):
        return [clean_multilang_fields(item) for item in data]
    return data


def migrate_sde_inplace(fsd_dir: Path | None = None) -> None:
    fsd_dir = fsd_dir or (SDE_PATH / "fsd")
    if not fsd_dir.exists():
        logger.warning("No fsd folder found at %s, skipping language pruning.", fsd_dir)
        return
    yaml_paths = sorted(fsd_dir.rglob("*.yaml"))
    logger.info("Pruning FSD language maps to supported languages: %s", ", ".join(_supported_languages()))
    if not yaml_paths:
        logger.info("No FSD YAML files found under %s; skipping language pruning.", fsd_dir)
        _progress_print("[SDE] pruning language maps skipped (no yaml files)", final=True)
        return
    _progress_print(f"[SDE] pruning language maps 0/{len(yaml_paths)}")
    loader = getattr(yaml, "CLoader", yaml.SafeLoader)
    for index, path in enumerate(yaml_paths, start=1):
        relative_path = path.relative_to(fsd_dir).as_posix()
        _progress_print(f"[SDE] pruning language maps {index}/{len(yaml_paths)} {relative_path}")
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = yaml.load(handle, Loader=loader)
            cleaned = clean_multilang_fields(data)
            with path.open("w", encoding="utf-8") as handle:
                yaml.safe_dump(cleaned, handle, allow_unicode=True)
        except Exception as exc:
            logger.error("Error pruning %s: %s", path, exc)
    logger.info("SDE language pruning complete.")
    _progress_print("[SDE] language pruning complete", final=True)


def rebuild_sde_warehouse(source_meta: dict | None = None) -> dict:
    source_meta = source_meta or {}
    _progress_print(f"[SDE] rebuilding warehouse at {sde_store.get_database_path()}")
    sde_loader.build_sde_warehouse(
        source_root=SDE_PATH,
        supported_languages=_supported_languages(),
        source_hash=source_meta.get("sha256"),
        source_zip_path=source_meta.get("zip_path"),
        source_etag=source_meta.get("etag"),
        source_last_modified=source_meta.get("last_modified"),
    )
    try:
        sde_store.sync_esi_registry_to_warehouse()
    except FileNotFoundError:
        logger.info("No ESI registry present yet; skipping DuckDB registry sync after SDE rebuild.")
    refresh_all_caches()
    _progress_print("[SDE] warehouse rebuild complete", final=True)
    return sde_store.get_warehouse_status()


def update_sde() -> dict:
    """Refresh the local SDE files, rebuild the DuckDB warehouse, and warm caches."""
    source_meta = download_sde()
    try:
        unzip_sde()
        migrate_sde_inplace()
        status = rebuild_sde_warehouse(source_meta)
    finally:
        cleanup()
    logger.info("SDE warehouse refreshed and caches warmed.")
    return status


def update_esi_spec() -> dict:
    """Refresh the versioned ESI OpenAPI registry."""
    return refresh_esi_spec_registry()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    update_sde()
