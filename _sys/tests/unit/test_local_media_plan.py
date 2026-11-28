"""Offline portal planning against explicitly supplied resource and canary receipts."""
import json
from pathlib import Path
import subprocess
import sys

import pytest


TOOLS = Path(__file__).resolve().parents[3] / "tools/feasibility"


def inventory():
    return {"schema_version": 1,
            "budget": {"ram_mib": 512, "scratch_mib": 1024, "cpu_threads": 4, "seconds": 120},
            "accelerators": [{"id": "device-1", "backend": "cuda", "vram_mib": 2048}],
            "receipts": []}


def receipt(capability, provider, **changes):
    return {"capability": capability, "provider": provider, "artifact_sha256": "a" * 64,
            "canary_sha256": "b" * 64, "model_sha256": None, "ram_mib": 100,
            "scratch_mib": 80, "cpu_threads": 2, "seconds": 10,
            "accelerator": None, "backend": "cpu", "vram_mib": 0} | changes


@pytest.fixture
def plan(monkeypatch):
    monkeypatch.syspath_prepend(str(TOOLS))
    from local_media_plan import plan
    return plan


def by_id(plan, host, **options):
    return {row["capability"]: row for row in plan(host, **options)}


def test_catalog_surfaces_distinct_format_delivery_and_manual_routes(plan):
    rows = by_id(plan, inventory())
    assert {row["family"] for row in rows.values()} == {"document", "image", "audio", "video", "web", "archive"}
    assert rows["office-structure"]["status"] == rows["office-layout"]["status"] == "NEEDS_LOCAL_PROOF"
    assert rows["hwp5-text"]["status"] == rows["hwpx-structure"]["status"] == "NEEDS_LOCAL_PROOF"
    assert rows["live-url"]["status"] == "MANUAL_INPUT"
    assert rows["speech-transcribe"]["status"] == rows["ocr-text"]["status"] == "OPT_IN"
    assert len(rows) == len(plan(inventory()))


def test_model_opt_in_and_evidence_never_implicitly_substitute_for_cpu(plan):
    host = inventory()
    host["receipts"] = [receipt("speech-transcribe", "faster-whisper"),
                        receipt("audio-transform", "ffmpeg")]
    assert by_id(plan, host)["speech-transcribe"]["status"] == "OPT_IN"
    options = {"enable": ["speech-transcribe"]}
    rows = by_id(plan, host, **options)
    assert rows["speech-transcribe"]["status"] == "NEEDS_LOCAL_MODEL"
    assert rows["audio-transform"]["status"] == "CPU_CANDIDATE"
    host["receipts"][0]["model_sha256"] = "c" * 64
    assert by_id(plan, host, **options)["speech-transcribe"]["status"] == "CPU_CANDIDATE"


def test_hardware_choice_requires_exact_device_and_fits_each_budget(plan):
    host = inventory()
    cpu = receipt("video-transcode", "ffmpeg")
    gpu = receipt("video-transcode", "ffmpeg", accelerator="device-1", backend="cuda", vram_mib=1000)
    host["receipts"] = [gpu, cpu]
    row = by_id(plan, host)["video-transcode"]
    assert row["status"] == "CPU_CANDIDATE" and row["selection"]["backend"] == "cpu"
    options = {"prefer_accelerator": True}
    row = by_id(plan, host, **options)["video-transcode"]
    assert row["status"] == "ACCELERATOR_CANDIDATE" and row["selection"]["accelerator"] == "device-1"
    host["accelerators"][0]["backend"] = "vulkan"
    assert by_id(plan, host, **options)["video-transcode"]["status"] == "CPU_CANDIDATE"
    host["budget"] = dict.fromkeys(host["budget"], 1)
    row = by_id(plan, host, **options)["video-transcode"]
    assert row["status"] == "RESOURCE_LIMIT"
    assert set(row["blockers"]) >= {"ram_mib", "scratch_mib", "cpu_threads", "seconds", "accelerator"}


def test_duplicate_and_unknown_receipts_and_invalid_limits_are_rejected(plan):
    entry = receipt("audio-transform", "ffmpeg")
    for receipts in ([entry, entry], [entry | {"provider": "cloud"}],
                     [entry | {"model_sha256": "c" * 64}], [entry | {"seconds": True}]):
        host = inventory()
        host["receipts"] = receipts
        with pytest.raises(ValueError):
            plan(host)
    with pytest.raises(ValueError):
        plan(inventory(), enable=["live-url"])


def test_json_cli_works_from_unrelated_directory_and_rejects_duplicate_keys(tmp_path):
    source = tmp_path / "host.json"
    source.write_text(json.dumps(inventory()), encoding="utf-8")
    args = [sys.executable, "-I", "-B", str(TOOLS / "local_media_plan.py"), str(source)]
    response = subprocess.run(args, cwd=tmp_path, capture_output=True, text=True, timeout=15)
    assert response.returncode == 0, response.stderr
    assert json.loads(response.stdout)["preview_only"] is True
    source.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
    response = subprocess.run(args, cwd=tmp_path, capture_output=True, text=True, timeout=15)
    assert response.returncode == 2 and not response.stdout
