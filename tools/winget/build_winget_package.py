#!/usr/bin/env python3
"""build_winget_package.py — Create Engram portable zip + Winget manifests.

Usage:
    python build_winget_package.py [--version 2.1.0] [--out-dir dist]

Produces:
    dist/Engram-v{VERSION}-portable-x64.zip   Portable distribution
    manifests/g/greatgc-flow/Engram/{VERSION}/ Winget YAML manifests
"""
from __future__ import annotations

import argparse
import hashlib
import os
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_VERSION = "2.1.0"
PACKAGE_ID = "greatgc-flow.Engram"
PUBLISHER = "greatgc-flow"
PACKAGE_NAME = "Engram"
LICENSE = "MIT"
HOMEPAGE = "https://github.com/greatgc-flow/Engram"
SCHEMA_VERSION = "1.9.0"

# Files and directories to INCLUDE in the portable zip (relative to repo root)
INCLUDE_FILES = [
    "Engram.exe",
    "INSTALL.bat",
    "UPDATE.bat",
    "STATUS.bat",
    "CLEANUP.bat",
    "TIDY.bat",
    "register.bat",
    "unregister.bat",
    "wrapper.cs",
    "README.md",
    "AGENTS.md",
    "GEMINI.md",
    "CLAUDE.md",
    "CONVENTION.md",
    "PROTOCOL.md",
    ".gitattributes",
    ".gitignore",
    ".agy",
    ".claude",
]

INCLUDE_DIRS = [
    # Only the lightweight core _sys subdirectories (~12 MB total)
    "_sys/ai",
    "_sys/checks",
    "_sys/cli",
    "_sys/config",
    "_sys/core",
    "_sys/docs",
    "_sys/docs-v2",
    "_sys/git-config",
    "_sys/hooks",
    "_sys/mock_peer",
    "_sys/templates",
    "_sys/tests",
]

# Additional files from _sys root to include
INCLUDE_SYS_FILES = [
    "_sys/runtimes.json",
]

# Patterns to exclude even within allowed directories
EXCLUDE_PATTERNS = [
    "__pycache__",
    ".pyc",
]


def should_exclude(rel_path: str) -> bool:
    """Check if a relative path matches any exclusion pattern."""
    normalized = rel_path.replace("\\", "/")
    for pattern in EXCLUDE_PATTERNS:
        if pattern in normalized:
            return True
    return False


def sha256_file(path: Path) -> str:
    """Compute SHA256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def build_zip(repo_root: Path, out_dir: Path, version: str) -> Path:
    """Build the portable zip distribution."""
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_name = f"Engram-v{version}-portable-x64.zip"
    zip_path = out_dir / zip_name

    # Remove old zip if exists
    if zip_path.exists():
        zip_path.unlink()

    prefix = f"Engram-v{version}/"
    count = 0

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        # Add individual root files
        for fname in INCLUDE_FILES:
            src = repo_root / fname
            if src.exists():
                arc_name = prefix + fname
                zf.write(src, arc_name)
                count += 1

        # Add individual _sys files
        for fname in INCLUDE_SYS_FILES:
            src = repo_root / fname
            if src.exists():
                arc_name = prefix + fname
                zf.write(src, arc_name)
                count += 1

        # Add directories recursively
        for dirname in INCLUDE_DIRS:
            src_dir = repo_root / dirname
            if not src_dir.is_dir():
                continue
            for root, dirs, files in os.walk(src_dir):
                rel_root = Path(root).relative_to(repo_root).as_posix()
                if should_exclude(rel_root):
                    dirs.clear()
                    continue
                # Filter out excluded subdirs
                dirs[:] = [d for d in dirs if not should_exclude(f"{rel_root}/{d}/")]
                for f in files:
                    rel_file = f"{rel_root}/{f}"
                    if should_exclude(rel_file):
                        continue
                    arc_name = prefix + rel_file
                    zf.write(Path(root) / f, arc_name)
                    count += 1

    print(f"[OK] Created {zip_path} ({count} files, {zip_path.stat().st_size / 1048576:.1f} MB)")
    return zip_path


def generate_manifests(manifest_dir: Path, version: str, sha256: str):
    """Generate the 4 Winget manifest YAML files."""
    manifest_dir.mkdir(parents=True, exist_ok=True)

    installer_url = f"https://github.com/greatgc-flow/Engram/releases/download/v{version}/Engram-v{version}-portable-x64.zip"

    # 1. Version manifest
    version_yaml = f"""# yaml-language-server: $schema=https://aka.ms/winget-manifest.version.{SCHEMA_VERSION}.schema.json
PackageIdentifier: {PACKAGE_ID}
PackageVersion: {version}
DefaultLocale: en-US
ManifestType: version
ManifestVersion: {SCHEMA_VERSION}
"""
    (manifest_dir / f"{PACKAGE_ID}.yaml").write_text(version_yaml, encoding="utf-8")

    # 2. Installer manifest
    installer_yaml = f"""# yaml-language-server: $schema=https://aka.ms/winget-manifest.installer.{SCHEMA_VERSION}.schema.json
PackageIdentifier: {PACKAGE_ID}
PackageVersion: {version}
InstallerType: zip
NestedInstallerType: portable
NestedInstallerFiles:
  - RelativeFilePath: Engram-v{version}\\Engram.exe
    PortableCommandAlias: engram
Commands:
  - engram
Installers:
  - Architecture: x64
    InstallerUrl: {installer_url}
    InstallerSha256: {sha256}
ManifestType: installer
ManifestVersion: {SCHEMA_VERSION}
"""
    (manifest_dir / f"{PACKAGE_ID}.installer.yaml").write_text(installer_yaml, encoding="utf-8")

    # 3. Default locale (en-US)
    locale_en_yaml = f"""# yaml-language-server: $schema=https://aka.ms/winget-manifest.defaultLocale.{SCHEMA_VERSION}.schema.json
PackageIdentifier: {PACKAGE_ID}
PackageVersion: {version}
PackageLocale: en-US
Publisher: {PUBLISHER}
PublisherUrl: https://github.com/greatgc-flow
PackageName: {PACKAGE_NAME}
PackageUrl: {HOMEPAGE}
License: {LICENSE}
ShortDescription: Portable multi-AI peer coordination environment for Windows
Description: |-
  Engram is a portable Windows development and AI-collaboration environment
  where multiple AI models (Claude, Gemini, Codex) act as equal governing
  peers on a peer-to-peer network. They cross-examine, dispute, and verify
  each other's work against strict logical invariants — nothing merges
  unless every active peer agrees.
Tags:
  - ai
  - collaboration
  - multi-agent
  - peer-review
  - portable
  - development-environment
  - claude
  - gemini
  - codex
ManifestType: defaultLocale
ManifestVersion: {SCHEMA_VERSION}
"""
    (manifest_dir / f"{PACKAGE_ID}.locale.en-US.yaml").write_text(locale_en_yaml, encoding="utf-8")

    # 4. Korean locale (ko-KR)
    locale_ko_yaml = f"""# yaml-language-server: $schema=https://aka.ms/winget-manifest.locale.{SCHEMA_VERSION}.schema.json
PackageIdentifier: {PACKAGE_ID}
PackageVersion: {version}
PackageLocale: ko-KR
Publisher: {PUBLISHER}
PublisherUrl: https://github.com/greatgc-flow
PackageName: {PACKAGE_NAME}
PackageUrl: {HOMEPAGE}
License: {LICENSE}
ShortDescription: 윈도우용 포터블 멀티-AI 피어 협업 개발 환경
Description: |-
  Engram은 여러 AI 모델(Claude, Gemini, Codex)이 P2P 네트워크에서
  동등한 거버닝 피어로 작동하는 포터블 Windows 개발/AI 협업 환경입니다.
  각 피어는 서로의 작업물을 교차 검증하고, 엄격한 논리적 불변 조건에 대해
  검사하며 — 모든 활성 피어가 동의하지 않으면 어떤 변경도 병합되지 않습니다.
Tags:
  - ai
  - 협업
  - 멀티-에이전트
  - 피어-리뷰
  - 포터블
  - 개발-환경
ManifestType: locale
ManifestVersion: {SCHEMA_VERSION}
"""
    (manifest_dir / f"{PACKAGE_ID}.locale.ko-KR.yaml").write_text(locale_ko_yaml, encoding="utf-8")

    print(f"[OK] Generated 4 manifest files in {manifest_dir}")
    for f in sorted(manifest_dir.iterdir()):
        print(f"     {f.name}")


def main():
    parser = argparse.ArgumentParser(description="Build Engram Winget package")
    parser.add_argument("--version", default=DEFAULT_VERSION, help="Package version")
    parser.add_argument("--out-dir", default="dist", help="Output directory for zip")
    parser.add_argument("--repo-root", default=".", help="Repository root directory")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    out_dir = repo_root / args.out_dir
    version = args.version

    print(f"=== Building Engram v{version} Winget Package ===")
    print(f"Repository root: {repo_root}")
    print()

    # Step 1: Build portable zip
    zip_path = build_zip(repo_root, out_dir, version)

    # Step 2: Compute SHA256
    sha256 = sha256_file(zip_path)
    print(f"[OK] SHA256: {sha256}")
    print()

    # Step 3: Generate manifests
    manifest_dir = repo_root / "manifests" / "g" / "greatgc-flow" / "Engram" / version
    generate_manifests(manifest_dir, version, sha256)
    print()

    # Step 4: Summary
    print("=== Build Complete ===")
    print(f"  Portable ZIP:  {zip_path}")
    print(f"  SHA256:        {sha256}")
    print(f"  Manifests:     {manifest_dir}")
    print()
    print("Next steps:")
    print(f"  1. Upload {zip_path.name} to GitHub Release v{version}")
    print(f"  2. Validate:  winget validate --manifest {manifest_dir}")
    print(f"  3. Test:      winget install --manifest {manifest_dir}")
    print(f"  4. Submit PR: fork microsoft/winget-pkgs, copy manifests/g/... into it")


if __name__ == "__main__":
    main()
