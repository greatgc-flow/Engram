"""Create a self-contained local media dashboard from inventory and exception JSON."""
import argparse
from base64 import b64encode
from hashlib import sha256
from html import escape
from pathlib import Path
import re
from string import Template
import sys
import unicodedata

HERE = Path(__file__).resolve().parent
if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
from local_media_plan import CATALOG, add_plan_options, plan, plan_options, read_local_json

ASSETS = HERE / "local_media_portal"
CAPABILITIES = {entry.id: entry.family for entry in CATALOG}
FAMILIES = {key: label for key, label in (
    ("document", "Documents"), ("image", "Images"), ("audio", "Audio"),
    ("video", "Video"), ("web", "Web files"), ("archive", "Archives"))}
DIMENSIONS = {"ram_mib": ("RAM", "MiB"), "scratch_mib": ("Scratch space", "MiB"),
              "cpu_threads": ("CPU threads", ""), "seconds": ("Time limit", "s"),
              "vram_mib": ("Device memory", "MiB"), "accelerator": ("Device / backend", "")}
STATUS = {
    "CPU_CANDIDATE": ("CPU candidate", "ready"),
    "ACCELERATOR_CANDIDATE": ("Accelerator candidate", "ready"),
    "NEEDS_LOCAL_PROOF": ("Needs evidence", "attention"),
    "NEEDS_LOCAL_MODEL": ("Needs local model", "attention"),
    "RESOURCE_LIMIT": ("Over budget", "attention"),
    "OPT_IN": ("Model opt-in", "optional"),
    "ACCELERATOR_OPT_IN": ("Accelerator opt-in", "optional"),
    "MANUAL_INPUT": ("Manual review", "manual"),
}
REASONS = {
    "fidelity-review": ("Fidelity review", "Compare this object with the original or an approved local rendering."),
    "missing-asset": ("Missing asset", "Locate the referenced asset locally and rerun the original operation."),
    "needs-ocr": ("OCR required", "Keep the source image and use separately approved local OCR for this region."),
    "unsupported": ("Unsupported input", "Keep the original and provide a supported local derivative for review."),
    "protected-input": ("Protected input", "Ask the owner for an authorized local copy or approved rendition."),
    "resource-limit": ("Resource limit", "Review the workload size and local resource budget before retrying."),
    "conversion-error": ("Conversion error", "Inspect the local conversion receipt and rerun after resolving the reported error."),
}
FINDING_FIELDS = {"source", "source_sha256", "capability", "locator", "reason", "detail"}
RESERVED = re.compile(r"(?:CON|PRN|AUX|NUL|COM[0-9¹²³]|LPT[0-9¹²³])", re.IGNORECASE)
DIGEST = re.compile(r"[a-f0-9]{64}")


def _text(value, limit):
    return (type(value) is str and 0 < len(value) <= limit and value == value.strip()
            and not any(unicodedata.category(ch) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for ch in value))


def _relative_source(value):
    return (_text(value, 512) and not any(ch in value for ch in '\\:<>"|?*')
            and all(part and not part.endswith((" ", ".")) and not RESERVED.fullmatch(part.split(".", 1)[0])
                    for part in value.split("/")))


def _findings(document):
    if (type(document) is not dict or document.keys() != {"schema_version", "findings"}
            or type(document["schema_version"]) is not int or document["schema_version"] != 1
            or type(document["findings"]) is not list or len(document["findings"]) > 1000):
        raise ValueError("invalid media exception report")
    rendered, sources, seen = [], {}, set()
    for row in document["findings"]:
        if (type(row) is not dict or row.keys() != FINDING_FIELDS or not _relative_source(row["source"])
                or not _text(row["locator"], 160) or not _text(row["detail"], 500)
                or not _text(row["source_sha256"], 64) or not DIGEST.fullmatch(row["source_sha256"])
                or not _text(row["capability"], 64) or row["capability"] not in CAPABILITIES
                or not _text(row["reason"], 64) or row["reason"] not in REASONS):
            raise ValueError("invalid media exception row")
        path, digest = row["source"], row["source_sha256"]
        identity = unicodedata.normalize("NFC", path).casefold()
        if sources.setdefault(identity, (path, digest)) != (path, digest):
            raise ValueError("conflicting media source identity")
        key = identity, row["capability"], row["locator"], row["reason"]
        if key in seen:
            raise ValueError("duplicate media exception")
        seen.add(key)
        label, action = REASONS[row["reason"]]
        rendered.append(row | {"label": label, "next_action": action})
    return sorted(rendered, key=lambda row: (row["source"].casefold(), row["locator"], row["reason"]))


def snapshot(host, findings=None, **options):
    capabilities = plan(host, **options)
    return {"budget": dict(host["budget"]), "accelerators": list(host["accelerators"]),
            "capabilities": capabilities, "report_supplied": findings is not None,
            "findings": [] if findings is None else _findings(findings)}


def _name(identifier):
    acronyms = {"hwp5": "HWP5", "hwpx": "HWPX", "pdf": "PDF", "ocr": "OCR", "html": "HTML", "url": "URL"}
    return " ".join(acronyms.get(word, word.capitalize()) for word in identifier.split("-"))


def _options(pairs):
    return "".join(f'<option value="{escape(key)}">{escape(label)}</option>' for key, label in pairs)


def _capability(row):
    label, group = STATUS[row["status"]]
    providers = ", ".join(row["providers"]) or "Local review"
    if row["blockers"]:
        constraint = ", ".join(DIMENSIONS[field][0] for field in row["blockers"])
        detail = f'<p><strong>Limits:</strong> {escape(constraint)}</p>'
    else:
        detail = ""
    selected = row["selection"]
    if selected:
        device = selected["accelerator"] or "CPU"
        detail += f'<p><strong>Selected:</strong> {escape(selected["provider"])} · {escape(device)}</p>'
        detail += ''.join(f'<p><strong>{label}:</strong> {selected[field]:,} {unit}</p>'
                          for field, (label, unit) in DIMENSIONS.items() if field != "accelerator")
        evidence = [("Artifact", selected["artifact_sha256"]), ("Canary", selected["canary_sha256"]),
                    ("Model", selected["model_sha256"])]
        detail += ''.join(f'<p><strong>{title}:</strong> <code>{escape(digest)}</code></p>'
                          for title, digest in evidence if digest)
    elif row["target_canary_sha256"]:
        detail += f'<p><strong>Requested canary:</strong> <code>{escape(row["target_canary_sha256"])}</code></p>'
    return f'''<details class="row" data-family="{row['family']}" data-status="{group}">
      <summary><span><strong>{escape(_name(row['capability']))}</strong><span class="sub">{escape(providers)}</span></span>
      <span class="pill {group}">{label}</span></summary>
      <div class="details"><p>{escape(row['next_action'])}</p>{detail}</div></details>'''


def _finding(row):
    return f'''<details class="row" data-reason="{row['reason']}">
      <summary><span><strong>{escape(row['source'].rsplit('/', 1)[-1])}</strong>
      <span class="sub">{escape(row['locator'])}</span></span><span class="pill attention">{row['label']}</span></summary>
      <div class="details"><p>{escape(row['detail'])}</p><p>{escape(row['next_action'])}</p>
      <p><strong>Capability:</strong> {escape(_name(row['capability']))}</p>
      <p><strong>Source:</strong> <code>{escape(row['source'])}</code></p>
      <p><strong>SHA-256:</strong> <code>{escape(row['source_sha256'])}</code></p></div></details>'''


def _hash_source(text):
    return "'sha256-" + b64encode(sha256(text.encode("utf-8")).digest()).decode("ascii") + "'"


def render(model):
    css = (ASSETS / "portal.css").read_text(encoding="utf-8")
    script = (ASSETS / "portal.js").read_text(encoding="utf-8")
    template = Template((ASSETS / "portal.html").read_text(encoding="utf-8"))
    candidates = sum(STATUS[row["status"]][1] == "ready" for row in model["capabilities"])
    budget = model["budget"]
    resources = ''.join(f'<div><dt>{label}</dt><dd>{budget[field]:,} <span>{unit}</span></dd></div>'
                        for field, (label, unit) in DIMENSIONS.items() if field in budget)
    devices = ', '.join(f'{row["id"]} · {row["backend"]} · {row["vram_mib"]:,} MiB'
                        for row in model["accelerators"])
    return template.substitute(css=css, script=script, css_hash=_hash_source(css), script_hash=_hash_source(script),
        candidate_count=candidates, capability_count=len(model["capabilities"]), resources=resources,
        device_summary=escape(devices or "No accelerator evidence supplied"),
        finding_count=len(model["findings"]) if model["report_supplied"] else "—",
        family_options=_options(FAMILIES.items()), reason_options=_options((key, data[0]) for key, data in REASONS.items()),
        capability_rows=''.join(_capability(row) for row in model["capabilities"]),
        finding_rows=''.join(_finding(row) for row in model["findings"]),
        finding_summary="Imported local findings" if model["report_supplied"] else "No exception report supplied",
        findings_hidden="hidden" if model["findings"] else "",
        finding_empty="No exceptions in this report." if model["report_supplied"] else "Generate a snapshot with a local exception report to review findings here.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path, help="reviewed local inventory JSON")
    parser.add_argument("--findings", type=Path, help="local exception report JSON")
    parser.add_argument("--output", type=Path, required=True, help="path for a new HTML file")
    add_plan_options(parser)
    args = parser.parse_args()
    try:
        if str(args.output).replace("\\", "/").startswith("//") or args.output.suffix.lower() != ".html":
            raise ValueError("output must be a local .html path")
        findings = read_local_json(args.findings, 512 * 1024) if args.findings is not None else None
        html = render(snapshot(read_local_json(args.inventory), findings, **plan_options(args)))
        with args.output.open("xb") as stream:
            stream.write(html.encode("utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
