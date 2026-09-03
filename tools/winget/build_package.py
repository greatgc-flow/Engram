#!/usr/bin/env python3
"""
build_package.py — Engram Winget Portable Packaging & Manifest Automation

Builds a clean, zero-bloat portable zip distribution of Engram and generates
official Microsoft Winget package manifests (Schema v1.6.0) under:
    manifests/g/greatgc-flow/Engram/<version>/

Usage:
    python tools/winget/build_package.py [--version 2.1.0] [--validate]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Sequence

# ── Package Metadata SSOT ───────────────────────────────────────────────────
PACKAGE_IDENTIFIER = "greatgc-flow.Engram"
PACKAGE_NAME = "Engram"
PUBLISHER = "greatgc-flow"
PUBLISHER_URL = "https://github.com/greatgc-flow"
PUBLISHER_SUPPORT_URL = "https://github.com/greatgc-flow/Engram/issues"
PACKAGE_URL = "https://github.com/greatgc-flow/Engram"
LICENSE = "MIT"
LICENSE_URL = "https://github.com/greatgc-flow/Engram/blob/main/LICENSE"
COPYRIGHT = "Copyright (c) 2026 greatgc-flow"
DEFAULT_LOCALE = "en-US"
SCHEMA_VERSION = "1.6.0"
DEFAULT_VERSION = "2.1.0"
try:
    _repo_root = Path(__file__).resolve().parent.parent.parent
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))
    from _sys.core.version import VERSION as DEFAULT_VERSION, WINGET_SCHEMA_VERSION as SCHEMA_VERSION
except ImportError:
    pass

MONIKER = "engram"

TAGS_EN = [
    "portable",
    "developer-tools",
    "workflow",
    "automation",
    "windows",
    "virtual-environment",
]

TAGS_KO = [
    "포터블",
    "개발도구",
    "자동화",
    "윈도우",
    "가상환경",
    "워크플로우",
]

SHORT_DESC_EN = "Portable Developer Runtime & Virtual Environment Engine for Windows"
DESC_EN = (
    "Engram is a zero-bloat, self-contained Windows portable runtime environment that "
    "provides virtual drive management and isolated Python/Node/Git environments. It can "
    "optionally install, update, and manage the status of third-party AI CLI tools, but all "
    "AI-to-AI collaboration itself is handled by the separate peerhub package."
)

SHORT_DESC_KO = "Windows용 무설치 포터블 개발 런타임 및 가상 환경 엔진"
DESC_KO = (
    "Engram은 가상 드라이브 관리(P:)와 격리된 Python/Node/Git 환경을 제공하는 "
    "Windows 전용 독립형 무설치 포터블 런타임 환경입니다. 서드파티 AI CLI 도구의 "
    "설치·업데이트·상태 확인을 선택적으로 지원하며, AI 간 협업 자체는 별도의 "
    "peerhub 패키지가 담당합니다."
)


def get_release_notes_en(version: str) -> str:
    return (
        f"Engram v{version}:\n"
        f"- Complete separation of Engram core from AI collaboration logic\n"
        f"- Native Winget portable package packaging support\n"
        f"- Zero-bloat portable developer runtime with isolated virtual environments"
    )


def get_release_notes_ko(version: str) -> str:
    return (
        f"Engram v{version} 릴리즈:\n"
        f"- Engram 코어와 AI 협업 로직의 완전한 분리 완료\n"
        f"- 공식 Winget 포터블 패키징 인프라 탑재\n"
        f"- 격리된 가상 환경을 갖춘 무설치 포터블 개발 런타임"
    )


# ── File Filter Rules for Clean Portable Archive ───────────────────────────
ROOT_FILES_ALLOW = {
    "engram.cmd",
    "INSTALL.bat",
    "STATUS.bat",
    "UPDATE.bat",
    "CLEANUP.bat",
    "TIDY.bat",
    "register.bat",
    "unregister.bat",
    "wrapper.cs",
    "Engram.exe",
    "LICENSE",
    "README.md",
    "CONVENTION.md",
}

SYS_EXCLUDE_DIR_PATTERNS = {
    "env",
    "tools",
    "temp",
    "logs",
    "state",
    "setup-files",
    "__pycache__",
    ".pytest_cache",
}

GLOBAL_EXCLUDE_PATTERNS = {
    ".git",
    ".gitattributes",
    ".gitignore",
    ".agy",
    ".ai",
    ".claude",
    ".codex",
    ".peerhub",
    ".vscode",
    "_archive",
    "output",
    "tmp",
    "workspace",
    "dist",
    "manifests",
}


def compute_sha256(file_path: Path) -> str:
    """Compute uppercase SHA256 hex digest of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


def collect_package_files(repo_root: Path) -> list[tuple[Path, str]]:
    """
    Collects relative file mappings (source_path, arcname) adhering to
    the zero-bloat portable runtime contract.
    """
    items: list[tuple[Path, str]] = []

    # 1. Root files
    for child in repo_root.iterdir():
        if child.is_file() and child.name in ROOT_FILES_ALLOW:
            items.append((child, child.name))

    # 2. _sys hierarchy
    sys_dir = repo_root / "_sys"
    if sys_dir.exists() and sys_dir.is_dir():
        for root, dirs, files in os.walk(sys_dir):
            rel_root = Path(root).relative_to(repo_root)

            # Filter out excluded directory segments
            parts = set(rel_root.parts)
            if parts.intersection(GLOBAL_EXCLUDE_PATTERNS):
                dirs.clear()
                continue
            if any(p in parts for p in SYS_EXCLUDE_DIR_PATTERNS):
                dirs.clear()
                continue

            # In-place directory pruning to avoid traversing excluded subtrees
            dirs[:] = [
                d for d in dirs
                if d not in SYS_EXCLUDE_DIR_PATTERNS
                and d not in GLOBAL_EXCLUDE_PATTERNS
                and not d.startswith(".")
            ]

            for file in files:
                if (
                    file.endswith(".pyc")
                    or file.endswith(".pyo")
                    or file.endswith(".tmp")
                    or file.endswith(".log")
                    or file == ".DS_Store"
                    or file.startswith(".git")
                ):
                    continue

                full_path = Path(root) / file
                arcname = str(full_path.relative_to(repo_root)).replace("\\", "/")
                items.append((full_path, arcname))

    # Sort deterministically for reproducible archives
    items.sort(key=lambda x: x[1])
    return items


def create_portable_archive(
    repo_root: Path,
    dist_dir: Path,
    version: str,
) -> tuple[Path, str, int, int]:
    """
    Creates the portable zip package and returns:
    (zip_path, sha256_uppercase, file_count, total_uncompressed_bytes)
    """
    dist_dir.mkdir(parents=True, exist_ok=True)
    zip_name = f"Engram-v{version}-portable-x64.zip"
    zip_path = dist_dir / zip_name

    file_items = collect_package_files(repo_root)
    total_uncompressed = sum(src.stat().st_size for src, _ in file_items)

    print(f"[PACK] Building portable bundle: {zip_path.name}")
    print(f"       Found {len(file_items)} files ({total_uncompressed / (1024 * 1024):.2f} MB uncompressed)")

    # Temporary zip write to ensure atomic replacement
    tmp_zip = zip_path.with_suffix(".tmp.zip")
    if tmp_zip.exists():
        tmp_zip.unlink()

    with zipfile.ZipFile(
        tmp_zip,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as zf:
        for src, arcname in file_items:
            zf.write(src, arcname)

    if zip_path.exists():
        zip_path.unlink()
    tmp_zip.rename(zip_path)

    sha256_hex = compute_sha256(zip_path)
    compressed_size = zip_path.stat().st_size
    ratio = (1.0 - (compressed_size / total_uncompressed)) * 100 if total_uncompressed > 0 else 0

    print(f"[PACK] Complete: {zip_path.name}")
    print(f"       Archive Size: {compressed_size / (1024 * 1024):.2f} MB ({ratio:.1f}% compression)")
    print(f"       SHA256: {sha256_hex}")

    return zip_path, sha256_hex, len(file_items), total_uncompressed


def generate_manifest_version(
    version: str,
    schema_version: str = SCHEMA_VERSION,
) -> str:
    return f"""# yaml-language-server: $schema=https://aka.ms/winget-manifest.version.{schema_version}.schema.json

PackageIdentifier: {PACKAGE_IDENTIFIER}
PackageVersion: {version}
DefaultLocale: {DEFAULT_LOCALE}
ManifestType: version
ManifestVersion: {schema_version}
"""


def generate_manifest_installer(
    version: str,
    sha256_hex: str,
    installer_url: str,
    schema_version: str = SCHEMA_VERSION,
) -> str:
    return f"""# yaml-language-server: $schema=https://aka.ms/winget-manifest.installer.{schema_version}.schema.json

PackageIdentifier: {PACKAGE_IDENTIFIER}
PackageVersion: {version}
InstallerType: zip
NestedInstallerType: portable
NestedInstallerFiles:
  - RelativeFilePath: Engram.exe
    PortableCommandAlias: engram
Installers:
  - Architecture: x64
    InstallerUrl: {installer_url}
    InstallerSha256: {sha256_hex}
ManifestType: installer
ManifestVersion: {schema_version}
"""


def generate_manifest_locale_en(
    version: str,
    schema_version: str = SCHEMA_VERSION,
) -> str:
    tags_formatted = "\n".join(f"  - {tag}" for tag in TAGS_EN)
    release_notes_indented = "\n".join(f"  {line}" for line in get_release_notes_en(version).splitlines())

    return f"""# yaml-language-server: $schema=https://aka.ms/winget-manifest.defaultLocale.{schema_version}.schema.json

PackageIdentifier: {PACKAGE_IDENTIFIER}
PackageVersion: {version}
PackageLocale: en-US
Publisher: {PUBLISHER}
PublisherUrl: {PUBLISHER_URL}
PublisherSupportUrl: {PUBLISHER_SUPPORT_URL}
PackageName: {PACKAGE_NAME}
PackageUrl: {PACKAGE_URL}
License: {LICENSE}
LicenseUrl: {LICENSE_URL}
Copyright: {COPYRIGHT}
CopyrightUrl: {LICENSE_URL}
ShortDescription: {SHORT_DESC_EN}
Description: {DESC_EN}
Moniker: {MONIKER}
Tags:
{tags_formatted}
ReleaseNotes: |-
{release_notes_indented}
ReleaseNotesUrl: {PACKAGE_URL}/releases/tag/v{version}
ManifestType: defaultLocale
ManifestVersion: {schema_version}
"""


def generate_manifest_locale_ko(
    version: str,
    schema_version: str = SCHEMA_VERSION,
) -> str:
    tags_formatted = "\n".join(f"  - {tag}" for tag in TAGS_KO)
    release_notes_indented = "\n".join(f"  {line}" for line in get_release_notes_ko(version).splitlines())

    return f"""# yaml-language-server: $schema=https://aka.ms/winget-manifest.locale.{schema_version}.schema.json

PackageIdentifier: {PACKAGE_IDENTIFIER}
PackageVersion: {version}
PackageLocale: ko-KR
Publisher: {PUBLISHER}
PublisherUrl: {PUBLISHER_URL}
PublisherSupportUrl: {PUBLISHER_SUPPORT_URL}
PackageName: {PACKAGE_NAME}
PackageUrl: {PACKAGE_URL}
License: {LICENSE}
LicenseUrl: {LICENSE_URL}
Copyright: {COPYRIGHT}
CopyrightUrl: {LICENSE_URL}
ShortDescription: {SHORT_DESC_KO}
Description: {DESC_KO}
Tags:
{tags_formatted}
ReleaseNotes: |-
{release_notes_indented}
ReleaseNotesUrl: {PACKAGE_URL}/releases/tag/v{version}
ManifestType: locale
ManifestVersion: {schema_version}
"""


def generate_manifests(
    manifest_dir: Path,
    version: str,
    sha256_hex: str,
    installer_url: str,
    schema_version: str = SCHEMA_VERSION,
) -> dict[str, Path]:
    """Writes all Winget manifest files under manifest_dir."""
    manifest_dir.mkdir(parents=True, exist_ok=True)

    files = {
        f"{PACKAGE_IDENTIFIER}.version.yaml": generate_manifest_version(version, schema_version),
        f"{PACKAGE_IDENTIFIER}.installer.yaml": generate_manifest_installer(version, sha256_hex, installer_url, schema_version),
        f"{PACKAGE_IDENTIFIER}.locale.en-US.yaml": generate_manifest_locale_en(version, schema_version),
        f"{PACKAGE_IDENTIFIER}.locale.ko-KR.yaml": generate_manifest_locale_ko(version, schema_version),
    }

    generated_paths: dict[str, Path] = {}
    print(f"\n[MANIFEST] Generating Winget manifests (Schema v{schema_version}):")
    for filename, content in files.items():
        out_path = manifest_dir / filename
        out_path.write_text(content, encoding="utf-8")
        generated_paths[filename] = out_path
        print(f"  + {out_path.relative_to(manifest_dir.parent.parent.parent.parent)}")

    return generated_paths


def validate_manifests_internal(manifest_paths: dict[str, Path], sha256_hex: str, version: str) -> list[str]:
    """Perform structural and semantic sanity checks on generated YAML manifests."""
    errors: list[str] = []

    for name, path in manifest_paths.items():
        if not path.exists():
            errors.append(f"Missing file: {name}")
            continue

        text = path.read_text(encoding="utf-8")
        if f"PackageIdentifier: {PACKAGE_IDENTIFIER}" not in text:
            errors.append(f"{name}: Missing or incorrect PackageIdentifier")
        if f"PackageVersion: {version}" not in text:
            errors.append(f"{name}: Missing or incorrect PackageVersion")

        if name.endswith(".installer.yaml"):
            if f"InstallerSha256: {sha256_hex}" not in text:
                errors.append(f"{name}: InstallerSha256 does not match computed checksum")
            if "NestedInstallerType: portable" not in text:
                errors.append(f"{name}: Missing NestedInstallerType: portable")
            if "PortableCommandAlias: engram" not in text:
                errors.append(f"{name}: Missing PortableCommandAlias: engram")

    return errors


def validate_with_winget_cli(manifest_dir: Path) -> tuple[bool, str]:
    """Run `winget validate --manifest <dir>` if winget CLI is available."""
    try:
        proc = subprocess.run(
            ["winget", "validate", "--manifest", str(manifest_dir)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        output = (proc.stdout + "\n" + proc.stderr).strip()
        return proc.returncode == 0, output
    except FileNotFoundError:
        return False, "winget CLI not found in PATH."
    except Exception as e:
        return False, f"winget validate error: {e}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Engram Winget Package & Manifest Builder",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--version",
        default=DEFAULT_VERSION,
        help="Target package version (e.g. 2.1.0)",
    )
    parser.add_argument(
        "--schema-version",
        default=SCHEMA_VERSION,
        help="Winget manifest schema version (e.g. 1.6.0 or 1.9.0)",
    )
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=Path("dist"),
        help="Directory to place the generated zip archive",
    )
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=None,
        help="Directory to place the generated manifests (defaults to manifests/g/greatgc-flow/Engram/<version>)",
    )
    parser.add_argument(
        "--installer-url",
        default=None,
        help="Public download URL for the installer zip",
    )
    parser.add_argument(
        "--skip-zip",
        action="store_true",
        help="Skip zip creation and reuse existing archive in dist-dir",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        default=True,
        help="Run validation on generated manifests",
    )
    parser.add_argument(
        "--no-validate",
        dest="validate",
        action="store_false",
        help="Disable manifest validation",
    )

    args = parser.parse_args(argv)

    # Resolve repo root relative to this script
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent

    # Setup directories
    dist_dir = (repo_root / args.dist_dir).resolve()
    version = args.version

    if args.manifest_dir:
        manifest_dir = (repo_root / args.manifest_dir).resolve()
    else:
        manifest_dir = (repo_root / "manifests" / "g" / "greatgc-flow" / "Engram" / version).resolve()

    installer_url = args.installer_url or (
        f"https://github.com/greatgc-flow/Engram/releases/download/v{version}/Engram-v{version}-portable-x64.zip"
    )

    print("=" * 78)
    print(f"  Engram Winget Package Builder — v{version}")
    print(f"  Root: {repo_root}")
    print("=" * 78)

    # 1. Package Zip Archive
    zip_name = f"Engram-v{version}-portable-x64.zip"
    zip_path = dist_dir / zip_name

    if args.skip_zip and zip_path.exists():
        print(f"[PACK] Skipping zip build; reusing {zip_path}")
        sha256_hex = compute_sha256(zip_path)
        print(f"       SHA256: {sha256_hex}")
    else:
        zip_path, sha256_hex, count, total_size = create_portable_archive(
            repo_root=repo_root,
            dist_dir=dist_dir,
            version=version,
        )

    # 2. Generate Winget Manifests
    manifest_paths = generate_manifests(
        manifest_dir=manifest_dir,
        version=version,
        sha256_hex=sha256_hex,
        installer_url=installer_url,
        schema_version=args.schema_version,
    )

    # 3. Validation
    if args.validate:
        print("\n[VALIDATION] Running Internal Schema & Semantic Checks...")
        internal_errors = validate_manifests_internal(manifest_paths, sha256_hex, version)
        if internal_errors:
            print("[ERROR] Internal validation failed:")
            for err in internal_errors:
                print(f"  - {err}")
            return 2
        print("  [OK] Internal structural and checksum checks passed.")

        print("\n[VALIDATION] Running official Microsoft WinGet CLI validator...")
        winget_ok, winget_out = validate_with_winget_cli(manifest_dir)
        if winget_ok:
            print("  [OK] WinGet CLI validation succeeded!")
        else:
            print(f"  [!] WinGet CLI validation message / output:\n{winget_out}")

    # 4. Deployment Instructions
    print("\n" + "=" * 78)
    print("  PACKAGE & MANIFEST ARTIFACTS READY FOR DISTRIBUTION")
    print("=" * 78)
    print(f"  Archive:       {zip_path}")
    print(f"  SHA256:        {sha256_hex}")
    print(f"  Manifest Dir:  {manifest_dir}")
    print("\n[Next Steps - Local Testing]")
    print(f"  winget install --manifest \"{manifest_dir}\"")
    print("\n[Next Steps - Upstream Winget PR Submission]")
    print("  1. Fork https://github.com/microsoft/winget-pkgs")
    print(f"  2. Copy manifests/g/greatgc-flow/Engram/{version} into manifests/g/greatgc-flow/Engram/{version}/")
    print(f"  3. Submit PR: 'Add greatgc-flow.Engram version {version}'")
    print("=" * 78)

    return 0


if __name__ == "__main__":
    sys.exit(main())
