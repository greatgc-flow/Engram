"""Preview local media capabilities from reviewed inventory and bounded canary receipts."""
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import stat


@dataclass(frozen=True)
class Capability:
    id: str
    family: str
    providers: tuple[str, ...]
    policy: str = "mechanical"


CATALOG = (
    Capability("plain-text", "document", ("markitdown-gc",)),
    Capability("office-structure", "document", ("markitdown-gc", "office-open-xml")),
    Capability("office-layout", "document", ("libreoffice",)),
    Capability("pdf-text", "document", ("pypdf", "markitdown-gc")),
    Capability("pdf-render", "document", ("poppler",)),
    Capability("hwp5-text", "document", ("markitdown-gc", "pyhwp")),
    Capability("hwpx-structure", "document", ("markitdown-gc", "hwpx-owpml-model")),
    Capability("hwp-layout-review", "document", (), "manual"),
    Capability("ocr-text", "document", ("tesseract",), "model"),
    Capability("image-raster", "image", ("pillow",)),
    Capability("image-vector", "image", ("resvg",)),
    Capability("image-metadata", "image", ("exiftool",)),
    Capability("image-visual-review", "image", (), "manual"),
    Capability("audio-transform", "audio", ("ffmpeg",)),
    Capability("speech-transcribe", "audio", ("faster-whisper", "whisper.cpp"), "model"),
    Capability("speech-synthesis", "audio", ("piper",), "model"),
    Capability("rule-speech", "audio", ("espeak-ng",)),
    Capability("video-inspect", "video", ("ffprobe",)),
    Capability("video-transcode", "video", ("ffmpeg",)),
    Capability("video-caption-mux", "video", ("ffmpeg",)),
    Capability("saved-html", "web", ("markitdown-gc",)),
    Capability("live-url", "web", (), "manual"),
    Capability("archive-inventory", "archive", ("python-zipfile", "ouch")),
)
_BY_ID = {feature.id: feature for feature in CATALOG}
_LIMITS = ("ram_mib", "scratch_mib", "cpu_threads", "seconds")
_HASH = re.compile(r"[0-9a-f]{64}")
_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_MAX_BYTES = 128 * 1024
_RECEIPT = set(_LIMITS) | {"capability", "provider", "artifact_sha256", "canary_sha256", "model_sha256",
                           "accelerator", "backend", "vram_mib"}
_ACTIONS = {
    "MANUAL_INPUT": "Preserve the original or provide an approved local input for review.",
    "OPT_IN": "Enable this capability explicitly before evaluating local model evidence.",
    "NEEDS_LOCAL_PROOF": "Supply an exact local artifact and a matching workload canary receipt.",
    "NEEDS_LOCAL_MODEL": "Supply reviewed local model or voice evidence for this canary.",
    "ACCELERATOR_OPT_IN": "Choose accelerator evaluation or supply a verified CPU canary.",
    "RESOURCE_LIMIT": "Review the resource shortfalls or use a smaller, separately measured workload.",
    "CPU_CANDIDATE": "Recheck resources and the exact workload before running.",
    "ACCELERATOR_CANDIDATE": "Recheck device resources and acquire the shared lease before running.",
}
_MANUAL_ACTIONS = {
    "hwp-layout-review": "Keep the original and compare it with an approved local rendering, including tables and shapes.",
    "image-visual-review": "Review the original pixels locally or opt in to OCR for text regions.",
    "live-url": "Provide an approved saved HTML file or local media file.",
}


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _matches(pattern, value):
    return type(value) is str and pattern.fullmatch(value) is not None


def _quantity(value):
    return type(value) is int and 0 <= value <= 2**40


def _valid_shape(row, fields):
    return type(row) is dict and row.keys() == set(fields)


def _load_inventory(host):
    _need(_valid_shape(host, ("schema_version", "budget", "accelerators", "receipts"))
          and type(host["schema_version"]) is int and host["schema_version"] == 1, "unknown inventory schema")
    budget, devices, receipts = (host[name] for name in ("budget", "accelerators", "receipts"))
    _need(_valid_shape(budget, _LIMITS) and all(_quantity(n) for n in budget.values()), "invalid resource budget")
    _need(type(devices) is list and len(devices) <= 32, "invalid accelerator inventory")
    accelerators = {}
    for row in devices:
        _need(_valid_shape(row, ("id", "backend", "vram_mib")) and _matches(_ID, row["id"])
              and _matches(_ID, row["backend"]) and row["backend"] != "cpu"
              and _quantity(row["vram_mib"]), "invalid accelerator evidence")
        key = row["id"], row["backend"]
        _need(key not in accelerators, "duplicate accelerator evidence")
        accelerators[key] = row["vram_mib"]

    _need(type(receipts) is list and len(receipts) <= 256, "invalid canary receipts")
    grouped = {feature.id: [] for feature in CATALOG}
    seen = set()
    for row in receipts:
        _need(_valid_shape(row, _RECEIPT) and _matches(_ID, row["capability"]), "invalid canary shape")
        feature = _BY_ID.get(row["capability"])
        _need(feature is not None and row["provider"] in feature.providers,
              "unknown capability or provider in canary")
        _need(all(_matches(_HASH, row[key]) for key in ("artifact_sha256", "canary_sha256"))
              and all(_quantity(row[key]) for key in (*_LIMITS, "vram_mib"))
              and row["seconds"] > 0 and row["cpu_threads"] > 0, "invalid canary measurements or digests")
        model, device, backend = (row[key] for key in ("model_sha256", "accelerator", "backend"))
        _need(model is None or (feature.policy == "model" and _matches(_HASH, model)), "invalid model evidence")
        _need((device is None and backend == "cpu" and row["vram_mib"] == 0)
              or (_matches(_ID, device) and _matches(_ID, backend) and backend != "cpu"), "invalid backend evidence")
        key = feature.id, row["provider"], row["artifact_sha256"], row["canary_sha256"], model, device, backend
        _need(key not in seen, "duplicate canary receipt")
        seen.add(key)
        grouped[feature.id].append(row)
    return budget, accelerators, grouped


def _shortfalls(row, budget, accelerators):
    fields = [field for field in _LIMITS if row[field] > budget[field]]
    if row["accelerator"] is not None:
        available = accelerators.get((row["accelerator"], row["backend"]))
        if available is None:
            fields.append("accelerator")
        elif row["vram_mib"] > available:
            fields.append("vram_mib")
    return fields


def _decision(feature, receipts, budget, accelerators, enable, prefer_accelerator):
    if feature.policy == "manual":
        return "MANUAL_INPUT", None, []
    if feature.policy == "model" and feature.id not in enable:
        return "OPT_IN", None, []
    if not receipts:
        return "NEEDS_LOCAL_PROOF", None, []
    proved = [row for row in receipts if feature.policy != "model" or row["model_sha256"] is not None]
    if not proved:
        return "NEEDS_LOCAL_MODEL", None, []
    allowed = [row for row in proved if prefer_accelerator or row["backend"] == "cpu"]
    if not allowed:
        return "ACCELERATOR_OPT_IN", None, []

    blockers = set()
    # Select an eligible accelerator first when requested, then rank by measured duration.
    for row in sorted(allowed, key=lambda r: (r["backend"] == "cpu", r["seconds"],
                                              feature.providers.index(r["provider"]), r["canary_sha256"],
                                              r["artifact_sha256"], r["model_sha256"] or "",
                                              r["accelerator"] or "", r["backend"])):
        shortfalls = _shortfalls(row, budget, accelerators)
        if not shortfalls:
            status = "CPU_CANDIDATE" if row["backend"] == "cpu" else "ACCELERATOR_CANDIDATE"
            return status, dict(row), []
        blockers.update(shortfalls)
    return "RESOURCE_LIMIT", None, sorted(blockers)


def plan(host, *, enable=(), prefer_accelerator=False, workloads=None):
    """Select an evidence-backed preview candidate per capability, without launching anything."""
    budget, devices, grouped = _load_inventory(host)
    _need(type(prefer_accelerator) is bool and type(enable) in (list, tuple)
          and all(_matches(_ID, item) and item in _BY_ID and _BY_ID[item].policy == "model" for item in enable),
          "unknown optional capability")
    workloads = {} if workloads is None else workloads
    _need(type(workloads) is dict and all(key in _BY_ID and _BY_ID[key].providers and _matches(_HASH, digest)
                                       for key, digest in workloads.items()), "invalid target canary")
    results = []
    for feature in CATALOG:
        target = workloads.get(feature.id)
        receipts = [row for row in grouped[feature.id] if target is None or row["canary_sha256"] == target]
        status, selection, blockers = _decision(feature, receipts, budget, devices, enable, prefer_accelerator)
        results.append({"capability": feature.id, "family": feature.family, "status": status,
                        "providers": list(feature.providers), "selection": selection,
                        "target_canary_sha256": target, "blockers": blockers,
                        "next_action": _MANUAL_ACTIONS.get(feature.id, _ACTIONS[status])})
    return results


def _unique(pairs):
    value = dict(pairs)
    _need(len(value) == len(pairs), "duplicate inventory key")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path, help="local reviewed inventory JSON")
    parser.add_argument("--enable", action="append", default=[], metavar="CAPABILITY")
    parser.add_argument("--prefer-accelerator", action="store_true")
    parser.add_argument("--canary", action="append", default=[], metavar="CAPABILITY=SHA256")
    args = parser.parse_args()
    try:
        _need(not str(args.inventory).replace("\\", "/").startswith("//"), "network paths are unsupported")
        info = args.inventory.lstat()
        _need(stat.S_ISREG(info.st_mode)
              and not getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT,
              "inventory must be an ordinary file")
        with args.inventory.open("rb") as stream:
            data = stream.read(_MAX_BYTES + 1)
        _need(len(data) <= _MAX_BYTES, "inventory exceeds size limit")
        host = json.loads(data.decode("utf-8"), object_pairs_hook=_unique)
        canaries = _unique([item.split("=", 1) for item in args.canary])
        rows = plan(host, enable=args.enable, prefer_accelerator=args.prefer_accelerator, workloads=canaries)
    except (OSError, ValueError, RecursionError) as exc:
        parser.error(str(exc))
    print(json.dumps({"schema_version": 1, "preview_only": True, "capabilities": rows}, sort_keys=True))


if __name__ == "__main__":
    main()
