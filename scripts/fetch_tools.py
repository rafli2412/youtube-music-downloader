#!/usr/bin/env python3
"""Acquire pinned desktop runtime tools at build time, never at app launch."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import platform
import shutil
import ssl
import stat
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "packaging" / "tool-manifest.json"
CHUNK_SIZE = 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_target(system: str = "auto", architecture: str = "auto") -> str:
    if system == "auto":
        system = {"Darwin": "macos", "Windows": "windows"}.get(platform.system(), "")
    if architecture == "auto":
        architecture = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64", "amd64": "x64"}.get(
            platform.machine().lower(), ""
        )
    target = f"{system}-{architecture}"
    if target not in {"macos-arm64", "windows-x64"}:
        raise ValueError(
            f"Unsupported target {target!r}. Phase 1 supports macos-arm64 and windows-x64."
        )
    return target


def validate_asset(asset: dict[str, Any]) -> None:
    """Require safe flat output paths and complete integrity metadata."""
    output = asset["output"]
    if not output or output in {".", ".."} or "/" in output or "\\" in output:
        raise ValueError(f"Unsafe output path: {output!r}")
    for field in ("sha256", "output_sha256"):
        value = asset[field]
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError(f"Invalid {field} for {output}")
    if not asset["url"].startswith("https://"):
        raise ValueError(f"Only HTTPS downloads are allowed: {asset['url']}")
    if asset["format"] not in {"raw", "gzip", "zip"}:
        raise ValueError(f"Unsupported archive format: {asset['format']}")
    if asset["format"] == "zip" and asset.get("member") not in {
        "deno",
        "deno.exe",
        "ffmpeg",
        "ffmpeg.exe",
        "ffprobe",
        "ffprobe.exe",
    }:
        raise ValueError("A pinned archive must name its exact executable member")


def download_asset(asset: dict[str, Any], cache: Path, context: ssl.SSLContext) -> Path:
    """Cache only downloads whose bytes match the committed upstream digest."""
    validate_asset(asset)
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / asset["sha256"]
    if destination.is_file() and sha256_file(destination) == asset["sha256"]:
        return destination
    request = urllib.request.Request(
        asset["url"], headers={"User-Agent": "youtube-music-downloader-build/0.1"}
    )
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=cache, prefix="download-", delete=False) as output:
            temporary = Path(output.name)
            with urllib.request.urlopen(request, context=context, timeout=90) as response:
                if not response.geturl().startswith("https://"):
                    raise ValueError("Refusing an insecure download redirect")
                shutil.copyfileobj(response, output, CHUNK_SIZE)
        if sha256_file(temporary) != asset["sha256"]:
            raise ValueError(f"Download checksum mismatch: {asset['output']}")
        temporary.replace(destination)
        return destination
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def install_asset(asset: dict[str, Any], archive: Path, destination: Path) -> Path:
    """Extract one exact member into a fixed filename; never unpack archive paths."""
    validate_asset(asset)
    destination.mkdir(parents=True, exist_ok=True)
    result = destination / asset["output"]
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination, prefix="install-", delete=False
        ) as output:
            temporary = Path(output.name)
            match asset["format"]:
                case "raw":
                    with archive.open("rb") as source:
                        shutil.copyfileobj(source, output, CHUNK_SIZE)
                case "gzip":
                    with gzip.open(archive, "rb") as source:
                        shutil.copyfileobj(source, output, CHUNK_SIZE)
                case "zip":
                    with zipfile.ZipFile(archive) as bundle:
                        matches = [
                            entry
                            for entry in bundle.infolist()
                            if entry.filename == asset["member"]
                        ]
                        if len(matches) != 1 or matches[0].is_dir():
                            raise ValueError(f"Expected exactly one {asset['member']} in archive")
                        mode = (matches[0].external_attr >> 16) & 0o170000
                        if mode == stat.S_IFLNK:
                            raise ValueError("Archive executable must not be a symbolic link")
                        with bundle.open(matches[0]) as source:
                            shutil.copyfileobj(source, output, CHUNK_SIZE)
        if sha256_file(temporary) != asset["output_sha256"]:
            raise ValueError(f"Extracted file checksum mismatch: {asset['output']}")
        if asset.get("executable"):
            temporary.chmod(0o755)
        else:
            temporary.chmod(0o644)
        temporary.replace(result)
        return result
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def verify_target(assets: list[dict[str, Any]], destination: Path) -> list[str]:
    failures = []
    for asset in assets:
        validate_asset(asset)
        path = destination / asset["output"]
        if not path.is_file():
            failures.append(f"Missing {path.name}")
        elif sha256_file(path) != asset["output_sha256"]:
            failures.append(f"Checksum mismatch: {path.name}")
        elif asset.get("executable") and os.name != "nt" and not os.access(path, os.X_OK):
            failures.append(f"Not executable: {path.name}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("auto", "macos", "windows"), default="auto")
    parser.add_argument("--arch", choices=("auto", "arm64", "x64"), default="auto")
    parser.add_argument(
        "--verify", action="store_true", help="Verify existing tools without network access"
    )
    parser.add_argument(
        "--list", action="store_true", help="List the pinned files without downloading"
    )
    parser.add_argument(
        "--ca-bundle", type=Path, help="Optional PEM CA bundle; TLS verification stays enabled"
    )
    args = parser.parse_args(argv)
    try:
        target = resolve_target(args.platform, args.arch)
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        assets = manifest["targets"][target]["assets"]
        destination = ROOT / "vendor" / target
        for asset in assets:
            validate_asset(asset)
        if args.list:
            for asset in assets:
                print(f"{asset['output']}: {asset['url']}")
            return 0
        if args.verify:
            failures = verify_target(assets, destination)
            for failure in failures:
                print(failure, file=sys.stderr)
            if not failures:
                print(f"Verified {len(assets)} pinned runtime files in {destination}")
            return int(bool(failures))
        context = ssl.create_default_context(cafile=str(args.ca_bundle) if args.ca_bundle else None)
        for asset in assets:
            existing = destination / asset["output"]
            if existing.is_file() and sha256_file(existing) == asset["output_sha256"]:
                if asset.get("executable"):
                    existing.chmod(0o755)
                print(f"Verified {asset['output']}", flush=True)
                continue
            print(f"Fetching {asset['output']}…", flush=True)
            downloaded = download_asset(asset, ROOT / "vendor" / ".downloads", context)
            install_asset(asset, downloaded, destination)
        receipt = {
            "schema_version": manifest["schema_version"],
            "target": target,
            "sources": manifest["sources"],
            "assets": assets,
        }
        # The committed manifest remains the authority; this copy travels with the app.
        receipt_path = destination / "tool-manifest.json"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(f"Runtime tools ready: {destination}")
        return 0
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        print(f"Runtime tool setup failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
