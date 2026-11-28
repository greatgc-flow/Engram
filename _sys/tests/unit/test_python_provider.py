"""WP1 provider admission and source/binary/consumer joins (R03, T59/T60)."""

from dataclasses import replace
from datetime import date, timedelta
import hashlib
import io
import tarfile

import pytest

from core import version_resolver

TODAY = date(2026, 11, 28)
TAG = "20261124"
API = "https://api.github.com/repos/astral-sh/python-build-standalone/releases"
WEB = "https://github.com/astral-sh/python-build-standalone/releases"


def upstream(version, digest="a" * 64, size=120, ident=100):
    name = f"cpython-{version}+{TAG}-x86_64-pc-windows-msvc-install_only.tar.gz"
    return {
        "name": name,
        "id": ident,
        "digest": "sha256:" + digest,
        "size": size,
        "state": "uploaded",
        "url": f"{API}/assets/{ident}",
        "browser_download_url": f"{WEB}/download/{TAG}/{name.replace('+', '%2B')}",
    }


def release_info():
    return {
        "url": API + "/21",
        "assets_url": API + "/21/assets",
        "id": 21,
        "html_url": WEB + "/tag/" + TAG,
        "tag_name": TAG,
        "immutable": True,
        "draft": False,
        "prerelease": False,
        "published_at": "2026-11-24T01:02:03Z",
    }


def discover(monkeypatch, assets, info=None, observed=TODAY):
    from core import python_provider as provider

    pages = []

    def fetch(url):
        pages.append(url)
        if url == API + "/latest":
            return release_info() if info is None else info
        n = len(pages) - 2
        assert url == API + f"/21/assets?per_page=100&page={n + 1}"
        return assets[100 * n : 100 * (n + 1)]

    monkeypatch.setattr(provider, "_read_api", fetch)
    return provider.fetch_release(today=observed), pages


def catalog(source="3.14.11", phase="SECURITY_ONLY", observed=TODAY):
    return {
        "observed_on": observed.isoformat(),
        "coverage": "MEASURED",
        "series": {
            "3.14": {
                "source_version": source,
                "support_phase": phase,
                "windows_binary": None,
                "compatible_candidate": None,
            }
        },
    }


def test_complete_release_pages_and_scoped_negative(monkeypatch):
    from core import python_provider as provider

    assets = [{"id": i + 1000, "name": f"notes-{i}"} for i in range(100)]
    assets += [upstream("3.14.9"), upstream("3.14.10", ident=101)]
    release, pages = discover(monkeypatch, assets)
    source = catalog()
    joined = provider.assess(source, release, {}, (), today=TODAY)
    row = joined["series"]["3.14"]
    assert row["windows_binary"] == "3.14.10"
    assert row["binary_status"] == "SOURCE_NEWER_NO_BINARY"
    assert row["compatible_candidate"] is None
    assert joined["binary_release"] == TAG and len(pages) == 3
    assert source["series"]["3.14"]["windows_binary"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("url", API.replace("astral-sh", "someone") + "/21"),
        ("immutable", False),
        ("draft", True),
        ("prerelease", True),
        ("id", True),
        ("published_at", "2027-01-01T00:00:00Z"),
        ("tag_name", "nightly"),
    ],
)
def test_release_requires_trusted_stable_origin(monkeypatch, field, value):
    from core import python_provider as provider

    info = {**release_info(), field: value}
    with pytest.raises(provider.ProviderError):
        discover(monkeypatch, [upstream("3.14.10")], info=info)


@pytest.mark.parametrize(
    "field,value",
    [
        ("digest", None),
        ("digest", "sha256:bad"),
        ("size", 0),
        ("state", "new"),
        ("url", API + "/assets/99"),
        ("browser_download_url", "https://example.invalid/asset"),
    ],
)
def test_incomplete_or_substituted_asset_cannot_prove_absence(monkeypatch, field, value):
    from core import python_provider as provider

    with pytest.raises(provider.ProviderError):
        discover(monkeypatch, [{**upstream("3.14.10"), field: value}])


def test_receipts_bind_every_current_consumer_and_full_build(monkeypatch):
    from core import python_provider as provider

    release, _ = discover(monkeypatch, [upstream("3.14.10")])
    artifact = release.artifacts[0]
    locks = {"app-one": "1" * 64, "app-two": "2" * 64}
    good = [provider.ConsumerReceipt(artifact, k, v, "PASS", "e" * 64) for k, v in locks.items()]

    def selected(receipts, source=None, snapshot=release, constraints=locks):
        return provider.assess(source or catalog(), snapshot, constraints, receipts, today=TODAY)["series"][
            "3.14"
        ]

    assert selected(good)["compatible_candidate"] == "3.14.10"
    assert selected(good[:1])["compatible_candidate"] is None
    for changed in (
        replace(good[1], lock_sha256="3" * 64),
        replace(good[1], evidence_sha256=""),
        replace(good[1], artifact=replace(artifact, sha256="b" * 64)),
    ):
        assert selected([good[0], changed])["compatible_candidate"] is None
    assert selected([*good, replace(good[0], outcome="FAIL")])["compatible_candidate"] is None
    assert selected(good, source=catalog(phase="EOL"))["compatible_candidate"] is None
    assert selected(good, source=catalog(phase="UNKNOWN"))["compatible_candidate"] is None
    assert selected(good, source=catalog(observed=TODAY - timedelta(days=1)))["compatible_candidate"] is None
    assert (
        selected(good, snapshot=replace(release, observed_on=TODAY - timedelta(days=1)))[
            "compatible_candidate"
        ]
        is None
    )


def test_partial_provider_failure_preserves_legacy_source(monkeypatch):
    from core import python_provider as provider

    source = {"status": "ok", "latest_patch_by_cycle": {"3.14": "3.14.10"}, "source_catalog": catalog()}
    monkeypatch.setattr(version_resolver, "_resolve_python", lambda *args, **kw: source.copy())

    def unavailable(*args, **kw):
        raise provider.ProviderError("public metadata unavailable")

    monkeypatch.setattr(provider, "fetch_release", unavailable)
    result = version_resolver.resolve_python_candidates()
    assert result["latest_patch_by_cycle"] == {"3.14": "3.14.10"}
    assert result["source_catalog"]["binary_coverage"] == "UNKNOWN"
    assert result["source_catalog"]["series"]["3.14"]["binary_status"] == "UNVERIFIABLE"


def make_archive(path, *, patch="3.14.10", machine=0x8664, dll="python314.dll"):
    pe = b"MZ" + bytes(58) + (64).to_bytes(4, "little") + b"PE\0\0" + machine.to_bytes(2, "little")
    contents = {
        "python/python.exe": pe,
        "python/" + dll: pe,
        "python/include/patchlevel.h": f'#define PY_VERSION "{patch}"\n'.encode(),
        "python/Lib/venv/__init__.py": b"# fixture",
        "python/Lib/ensurepip/__init__.py": b"# fixture",
        "python/Lib/ensurepip/_bundled/pip-1.0-py3-none-any.whl": b"placeholder",
        "python/LICENSE.txt": b"fixture",
    }
    with tarfile.open(path, "w:gz") as tar:
        for name, raw in contents.items():
            m = tarfile.TarInfo(name)
            m.size = len(raw)
            tar.addfile(m, io.BytesIO(raw))


@pytest.mark.parametrize(
    "patch,machine,dll,ok",
    [
        ("3.14.10", 0x8664, "python314.dll", True),
        ("3.14.9", 0x8664, "python314.dll", False),
        ("3.14.10", 0x14C, "python314.dll", False),
        ("3.14.10", 0x8664, "python314t.dll", False),
    ],
)
def test_admission_checks_bytes_and_packaging_without_install(monkeypatch, tmp_path, patch, machine, dll, ok):
    from core import python_provider as provider
    from core import python_artifact

    path = tmp_path / "cache"
    make_archive(path, patch=patch, machine=machine, dll=dll)
    data = path.read_bytes()
    release, _ = discover(monkeypatch, [upstream("3.14.10", hashlib.sha256(data).hexdigest(), len(data))])
    artifact = release.artifacts[0]
    if ok:
        result = python_artifact.verify_cached(path, artifact, artifact.identity())
        assert result["regular_files"] == 7
        assert result["python_pe_machine"] == "AMD64"
        for field in (
            "provider",
            "flavor",
            "arch",
            "implementation",
            "version",
            "abi",
            "sha256",
            "artifact_ref",
        ):
            with pytest.raises(provider.ProviderError):
                python_artifact.verify_cached(path, artifact, {**artifact.identity(), field: "other"})
        path.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
    with pytest.raises(provider.ProviderError):
        python_artifact.verify_cached(path, artifact, artifact.identity())
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize(
    "name",
    [
        "../outside",
        "python/../other",
        "C:/tool",
        "python/AUX.txt",
        "python/bin:alias",
        "python/dir./tool",
        "python/back\\slash",
        "python//name",
        "other/tool",
    ],
)
def test_windows_member_names_rejected_before_extraction(name):
    from core import python_artifact

    with pytest.raises(python_artifact.ProviderError):
        python_artifact.validate_member_name(name)


def test_partial_page_failure_and_ambiguous_inventory(monkeypatch):
    from core import python_provider as provider

    duplicate = upstream("3.14.10")
    with pytest.raises(provider.ProviderError, match="ambiguous"):
        discover(monkeypatch, [duplicate, duplicate.copy()])
    with pytest.raises(provider.ProviderError, match="incomplete"):
        discover(monkeypatch, [], info={**release_info(), "assets": [duplicate]})

    def read(url):
        if url.endswith("/latest"):
            return release_info()
        if url.endswith("page=1"):
            return [{"name": f"notice-{i}", "id": i + 1} for i in range(100)]
        raise provider.ProviderError("second page unavailable")

    monkeypatch.setattr(provider, "_read_api", read)
    with pytest.raises(provider.ProviderError, match="second page"):
        provider.fetch_release(today=TODAY)


def test_foreign_variants_do_not_qualify(monkeypatch):
    from core import python_provider as provider

    variants = ["3.14.10rc1", "3.14.10t", "2.7.18"]
    assets = [upstream(version, ident=i + 1) for i, version in enumerate(variants)]
    for i, other in enumerate(["aarch64", "i686", "x86_64_v3"]):
        asset = upstream("3.14.10", ident=10 + i)
        asset["name"] = asset["name"].replace("x86_64", other)
        assets.append(asset)
    release, _ = discover(monkeypatch, assets)
    row = provider.assess(catalog(), release, {}, [], today=TODAY)["series"]["3.14"]
    assert row["windows_binary"] is None
    assert row["compatible_candidate"] is None


def test_catalog_skew_and_partial_cycle_evidence(monkeypatch):
    from core import python_provider as provider

    release, _ = discover(monkeypatch, [upstream("3.14.10")])
    old = catalog(source="3.14.9")
    assert (
        provider.assess(old, release, {}, [], today=TODAY)["series"]["3.14"]["binary_status"]
        == "UNVERIFIABLE"
    )
    for incomplete in (["3.14"], None):
        src = {**catalog(), "coverage": "PARTIAL", "incomplete_series": incomplete}
        row = provider.assess(src, release, {}, [], today=TODAY)["series"]["3.14"]
        assert row["binary_status"] == "UNVERIFIABLE"
        assert row["compatible_candidate"] is None
    assert provider.assess({"series": None}, release, {}, (), today=TODAY)["series"] == {}


def test_admitted_snapshot_survives_cache_replacement(tmp_path, monkeypatch):
    from core import python_artifact

    path = tmp_path / "download"
    make_archive(path)
    data = path.read_bytes()
    release, _ = discover(monkeypatch, [upstream("3.14.10", hashlib.sha256(data).hexdigest(), len(data))])
    subject = release.artifacts[0]
    with python_artifact.open_verified(path, subject, subject.identity()) as (verified, receipt):
        path.write_bytes(b"new unverified cache contents")
        assert verified.read() == data
        assert receipt["identity"] == subject.identity()


@pytest.mark.parametrize(
    "rows",
    [
        [("python/sample", tarfile.SYMTYPE)],
        [("python/sample", tarfile.LNKTYPE)],
        [("python/sample", tarfile.FIFOTYPE)],
        [("python/sample", tarfile.REGTYPE)] * 2,
        [("python/Lib/a", tarfile.REGTYPE), ("python/lib/b", tarfile.REGTYPE)],
        [("python/Lib/a", tarfile.REGTYPE), ("python/Lib", tarfile.REGTYPE)],
    ],
)
def test_member_metadata_refused_without_extraction(rows):
    from core import python_artifact

    # Header-only fixtures exercise validation without creating or extracting member paths.
    members = []
    for name, kind in rows:
        member = tarfile.TarInfo(name)
        member.type = kind
        members.append(member)
    artifact = python_artifact.Artifact(TAG, "3.14.10", 1, "0" * 64, 1)
    with pytest.raises(python_artifact.ProviderError, match="member|collision"):
        python_artifact._inspect_members(members, artifact, 1024)


def test_candidate_provider_records_separate_installed_inventory(tmp_path, monkeypatch):
    from core import python_provider as provider

    monkeypatch.setattr(
        version_resolver, "_resolve_python", lambda *a, **kw: {"status": "ok", "source_catalog": catalog()}
    )
    release, _ = discover(monkeypatch, [upstream("3.14.10")])
    monkeypatch.setattr(provider, "fetch_release", lambda: release)
    root = tmp_path / "absent-system"
    result = version_resolver.resolve_python_candidates(registry_root=root)
    assert result["installed"]["revision"] == 0
    assert result["installed"]["series"] == {}
    assert result["installed"]["legacy"]["status"] == "ABSENT"
    assert not root.exists()


def test_windows_tcl_timezone_name_with_plus_is_valid():
    from core.python_artifact import validate_member_name

    name = "python/tcl/tcl8.6/tzdata/Etc/GMT+1"
    assert validate_member_name(name) == name.split("/")
