#!/usr/bin/env python3
"""Reject Mac bundles whose native code requires a newer OS than their Info.plist."""

from __future__ import annotations

import argparse
import json
import platform
import plistlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MACH_O_MAGIC = {
    b"\xfe\xed\xfa\xce",
    b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
    b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe",
    b"\xbe\xba\xfe\xca",
    b"\xca\xfe\xba\xbf",
    b"\xbf\xba\xfe\xca",
}


def version_tuple(value: str) -> tuple[int, ...]:
    parts = tuple(int(part) for part in value.split("."))
    if not 1 <= len(parts) <= 3 or any(part < 0 for part in parts):
        raise ValueError(f"Invalid macOS version: {value}")
    return parts + (0,) * (3 - len(parts))


def minimum_versions(load_commands: str) -> list[str]:
    """Read deployment targets, excluding SDK and linker-tool version fields."""
    command = ""
    macos = False
    versions = []
    for line in load_commands.splitlines():
        fields = line.split()
        if len(fields) != 2:
            continue
        field, value = fields
        if field == "cmd":
            command = value
            macos = False
        elif command == "LC_BUILD_VERSION" and field == "platform":
            macos = value in {"MACOS", "1"}
        elif (command == "LC_BUILD_VERSION" and macos and field == "minos") or (
            command == "LC_VERSION_MIN_MACOSX" and field == "version"
        ):
            version_tuple(value)
            versions.append(value)
        elif command == "LC_BUILD_VERSION" and field == "ntools":
            command = ""  # Subsequent `version` fields describe build tools.
    return versions


def audit_bundle(bundle: Path) -> dict:
    with (bundle / "Contents/Info.plist").open("rb") as source:
        declared = plistlib.load(source)["LSMinimumSystemVersion"]
    target = version_tuple(declared)
    required = target
    checked = 0
    violations = []
    for path in sorted(bundle.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        with path.open("rb") as source:
            if source.read(4) not in MACH_O_MAGIC:
                continue
        checked += 1
        relative = path.relative_to(bundle).as_posix()
        process = subprocess.run(
            ["/usr/bin/otool", "-arch", "arm64", "-l", str(path)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        versions = minimum_versions(process.stdout) if process.returncode == 0 else []
        if not versions:
            violations.append({"path": relative, "error": "No Apple Silicon macOS target found"})
            continue
        newest = max(versions, key=version_tuple)
        required = max(required, version_tuple(newest))
        if version_tuple(newest) > target:
            violations.append({"path": relative, "minimum_macos": newest})
    return {
        "ok": checked > 0 and not violations,
        "declared_minimum_macos": declared,
        "required_minimum_macos": ".".join(str(part) for part in required),
        "binaries_checked": checked,
        "violations": violations,
        "scope": "Static deployment-target audit; not execution on the minimum OS version.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument(
        "--report", type=Path, default=ROOT / "build/reports/macos-compatibility.json"
    )
    args = parser.parse_args()
    if platform.system() != "Darwin":
        parser.error("This check requires macOS and its otool command.")
    report = audit_bundle(args.bundle.resolve())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not report["ok"]:
        print("Rebuild with Python and dependencies supporting the declared macOS minimum.")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
