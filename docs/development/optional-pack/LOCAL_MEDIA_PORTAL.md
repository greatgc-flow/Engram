# Local media capability and resource preview

Engram owns portable runtime evidence, shared resource checks and package lifecycle. ContentFlow owns media workflows, authoritative originals, derived artifacts and editorial review. markitdown-gc remains an independent local extraction adapter. ContentFlow can use its own approved local tools without an Engram import. Use the same status and evidence fields in a future portal, command line or exported report.

## Capability review

Each row distinguishes an input family, an operation and the evidence needed for its result. Text, machine-readable objects, rendered pages and inferred text are different deliverables. Preserve the input hash, media type and a page, slide, cell, object, frame or time locator. A mixed document may have both a completed native extraction and individual objects awaiting review.

| Family | Local mechanical path | Optional or exception path | Evidence |
| --- | --- | --- | --- |
| Markdown, text, CSV, saved HTML | Read native text and tables. Retain heading, line and row provenance. Use markitdown-gc only on approved local input. | Encoding, malformed markup and external references need explicit findings. Preserve remote links as text. Report missing local assets. | Fixture checks exact rows, relative assets, and no network. |
| DOCX, PPTX, XLSX, legacy Office | Extract native text, tables and available Open XML chart series, labels, shapes and embedded media. Open XML package data can supplement Markdown output. LibreOffice headless is a separate derived rendering or legacy-conversion lane. | Externally linked series, scatter/combo charts, unsupported drawing objects, formula caches and font substitution need object-level findings. Preserve the original and extract or render supported objects independently. | Compare chart values and locators, table spans, shape text and images. Compare rendered pages/slides separately and record fonts. Block macros and external link refresh. |
| PDF | pypdf or markitdown-gc for embedded text. Poppler for page pixels. | Scanned, blank, text-under-image or mixed pages require per-page coverage. OCR only with explicit local Tesseract and reviewed language data. A page image does not supply verified text. | Distinguish embedded text, rendering, image-only and unresolved pages. Verify page count and orientation. |
| HWP5 and HWPX | Reuse markitdown-gc's local parser for supported text, tables, notes and media. pyhwp is a candidate HWP5 reader. Hancom's OWPML model is a candidate HWPX reference. | Encrypted, distribution-protected, pre-HWP5, unsupported layout, charts, headers and grouped drawings need separate findings. Preserve the original and permit a reviewed local PDF rendition. | Verify per-object structure, Korean text, assets and explicit omissions. Legacy LibreOffice coverage depends on the exact input and is derived. |
| Images | Pillow for bounded raster operations, resvg for local SVG rendering, ExifTool for metadata. Preserve ICC, alpha, orientation and frame properties when required. | Unavailable HEIC/RAW/animated decoder, external SVG resource, image meaning and visual similarity require separate evidence. Pixel text is separately opted-in OCR. | Exact dimensions, frames, expected pixels and metadata. Bound decompressed pixels and deny external delegates and URL resources. |
| Audio | FFmpeg for codec, sample rate, channel conversion and loudness. eSpeak NG is a candidate rule-based TTS adapter for independently checked voices. | faster-whisper or whisper.cpp with locally verified assets for STT. Piper with a separately licensed local voice for neural TTS. Missing language, voice, timing or quality evidence remains visible. | Decode, offsets, loudness and sample properties. Test intelligibility, Korean names, punctuation and timestamp error separately. |
| Video | FFprobe for container/stream inventory. FFmpeg for bounded local transcode, thumbnail, crop and subtitle mux. Reuse standalone ContentFlow CPU proof. | Missing codec, HDR/alpha/subtitle/font fidelity or hardware limits block the relevant operation. STT is a separate audio capability. Live URLs and YouTube go to local input review. | Inspect streams, then decode full fixture and validate frame count, audio, subtitle timing and artifact hashes. |
| Archives and live input | List ZIP entries using Python or Ouch, within explicit depth and size limits. Parse saved files independently. | Password, reparse entry, nested expansion, traversal, unsupported format or a URL without a local file gets an exception. | Assert member inventory and resource ceilings. Never make archive listing an implicit extraction request. |

Reviewed [markitdown-gc at `74d76fb`](https://github.com/greatgc-flow/markitdown-gc/tree/74d76fb2e15c755a6a5237bac54b42511fc936fc). Its PPTX converter emits chart data for supported chart types and `[unsupported chart]` otherwise. Its HWP extraction and OCR report expose bounded kinds of content. Its README documents cases where Markdown conversion can return an empty derivative for scans. Treat `[unsupported chart]`, image placeholders, empty text and partial coverage as findings. Inspect output coverage even when the conversion exits successfully. Keep cloud OCR and network-backed transcribers outside this local profile.

## Resource profiles and portal presentation

| Profile | Evidence and behavior |
| --- | --- |
| Mechanical CPU | Default planning mode. Report exact available operations. Use bounded per-operation CPU, scratch, RAM and wall-time limits. Heavy render jobs can stay pending while interactive work is active. |
| Optional local inference | Explicitly enable each of `ocr-text`, `speech-transcribe` and `speech-synthesis`. Supply exact local model or voice identity and a workload receipt. Start with a CPU canary when available. Use a local model directory and download-disabled configuration for faster-whisper. |
| Optional acceleration | Require an explicitly preferred, measured device and backend pair with verified local support and free device resources. A fitting CPU receipt is a valid fallback. Before execution acquire the existing shared resource lease and recheck availability. A single GPU model is not a platform requirement. |

Show the requested capability, status, exact artifact/canary, limiting dimensions and actionable next step. The preview distinguishes `NEEDS_LOCAL_PROOF`, `NEEDS_LOCAL_MODEL`, `OPT_IN`, `ACCELERATOR_OPT_IN`, `RESOURCE_LIMIT`, `MANUAL_INPUT`, `CPU_CANDIDATE` and `ACCELERATOR_CANDIDATE`. A future item queue should show source and locator, missing content, fidelity and retry requirements. Keep original evidence accessible from each exception. For mixed inputs, record complete results independently and keep the incomplete parts visible.

Supply measured free/available RAM and scratch after headroom, granted CPU threads and the wall-time limit for a single job. Accelerator entries identify an observed device and backend and usable device memory. A receipt records measured peak RAM, maximum scratch, granted CPU threads and rounded wall seconds for one exact canary. Receipts carry artifact, canary and optional model digests. Canary identity needs to cover the format subtype, asset size, codec, resolution, duration and settings that drive the measured envelope. There is no fixed workstation RAM or VRAM recommendation based on the tool name alone. Concurrent jobs need aggregate admission and fresh resource evidence before dispatch.

## Run the preview

From an Engram source checkout, create a reviewed local JSON file using the following illustrative budget. An empty receipt list shows the unmet evidence without reading any input documents.

```json
{
  "schema_version": 1,
  "budget": {"ram_mib": 4096, "scratch_mib": 8192, "cpu_threads": 4, "seconds": 180},
  "accelerators": [],
  "receipts": []
}
```

```sh
python -I -B tools/feasibility/local_media_plan.py host.json
python -I -B tools/feasibility/local_media_plan.py host.json --enable speech-transcribe
python -I -B tools/feasibility/local_media_plan.py host.json --prefer-accelerator --canary video-transcode=REVIEWED_SHA256
```

Each receipt accepts `capability`, `provider`, `artifact_sha256`, `canary_sha256`, `model_sha256`, `ram_mib`, `scratch_mib`, `cpu_threads`, `seconds`, `accelerator`, `backend` and `vram_mib`. Use `null`, `cpu` and zero device MiB for a CPU receipt. Use `null` for a mechanical operation's model digest. Omit the target canary to get an inventory overview. Pin it to see whether that exact workload fits. Output is read-only JSON and `preview_only` is always true. Digests identify the reviewed evidence supplied by the caller. Independent artifact verification, a fresh resource snapshot, execution isolation and the production trust gate still apply before dispatch.

## Tool admission and verification

- Reuse ContentFlow's verified CPU fixture before onboarding native Windows codecs. FFmpeg options determine the actual redistribution terms. Pin executable and companion tools, build configuration, notices and font identity. Prefer bounded local input/protocol allowlists.
- Pin and test document engines in their own app environments. Keep the core package-free. Use local temporary profiles, suppress macros and external assets, and bound parser resources before opting in. Record original and derived file hashes, missing objects and fidelity.
- Treat engines, models, voices and codecs as independent artifacts. Piper's engine and voice licensing are separate. Approve a specific voice's redistribution and Korean quality before offering it. GPU and camera/voice collection require their own evidence and permissions.
- The preview tests are synthetic. Current local media evidence comes from the actual ContentFlow FFmpeg full decode/corruption test. Runtime installation, a live portal, Korean OCR, STT/TTS models and GPU workloads have their own acceptance gates.

## Upstream references

- [LibreOffice command-line options](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html), [pypdf extraction limits](https://pypdf.readthedocs.io/en/stable/user/extract-text.html), [Hancom OWPML reference implementation](https://github.com/hancom-io/hwpx-owpml-model), [pyhwp](https://github.com/mete0r/pyhwp).
- [Pillow image handling](https://pillow.readthedocs.io/en/stable/reference/Image.html), [resvg](https://github.com/linebender/resvg), [ExifTool](https://exiftool.org/), [Tesseract language data](https://tesseract-ocr.github.io/tessdoc/Data-Files-in-different-versions.html).
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [whisper.cpp](https://github.com/ggml-org/whisper.cpp), [Piper licensing](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/LICENSING.md), [eSpeak NG languages](https://github.com/espeak-ng/espeak-ng/blob/master/docs/languages.md).
- [FFmpeg license and build conditions](https://www.ffmpeg.org/legal.html), [FFmpeg protocol options](https://www.ffmpeg.org/ffmpeg-protocols.html).
