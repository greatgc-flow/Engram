# Accelerator qualification across Windows hosts

This amendment governs new development against Rev. 0.6. The named RTX 3060, Ryzen and memory sizes in the frozen specification describe one reference machine. Engram installation, Multi-Python, and optional AI discovery have no GPU model requirement. A profile qualifies on evidence for the workload on the current host. A missing device or backend blocks only the affected profile.

## Observation before qualification

Run `python -B tools/feasibility/windows_accelerators.py` for an opt-in local display-controller inventory. It returns machine-readable JSON, an adapter name and driver when supplied, and the source and coverage. An empty successful query differs from unavailable telemetry. Duplicate names retain separate rows. Inventory order and marketing names cannot identify a device across restarts. The probe runs no inference, installs no driver, reports no hardware serial or device instance ID and reads no private activity. Its Windows CIM source enumerates display controllers; headless compute devices may require backend discovery.

Keep these observations separate in future WP4/WP5/WP8 implementations:

| Evidence | Required interpretation |
|---|---|
| OS inventory | Display controllers observed locally. Driver-reported adapter RAM is unsuitable for admission. The CIM AdapterRAM property is a 32-bit field. |
| Backend enumeration | Probe the installed backend and supported device selection mechanism. Correlate physical adapter identities within the current boot. Two backends can refer to the same GPU. Ambiguous attribution cannot establish separate capacity. |
| Resident model and placement | Record backend version, driver, selected device set, model digest, quantization, context, KV settings, offload arrangement and observed execution. A listed adapter does not prove model allocation. |
| Memory | Measure applicable per-device budget and use, host RAM/commit and a reserve in bytes. DXGI process budgets and usage have process scope. Backend-owned allocations need evidence from the backend process. Unknown, stale or inconsistent samples block new accelerator leases. |
| Workload | Run synthetic warm/cold inference, effective context allocation, output quality and interactive latency for the requested role. Keep measurements and admission decisions scoped to that exact profile. |

## Selection and scheduling decisions

1. Discover available CPU and accelerator backends only on explicit AI setup/check. Keep doctor local and read-only. CPU-only installations retain all independent Engram functions. Offer CPU inference only when the local backend supports it, the workload qualifies and the user's policy permits that mode.
2. Evaluate NVIDIA, AMD, Intel, integrated and other adapters using the same evidence contract. Choose only a backend/device pairing the installed version exposes. Optional or experimental backends require explicit opt-in and the same workload checks. Installing a driver or changing a system-wide backend setting is outside discovery.
3. Treat integrated/shared memory as one physical budget shared with host work. Never add a reported shared-memory ceiling to system RAM. Keep discrete adapter budgets separate. Multiple GPUs require successful placement on each participating device. Summing nominal VRAM does not qualify a split model.
4. Use a shared scheduler across agents, retrieval, embeddings and sleep. Initially admit one GPU work unit at a time. Permit independent parallel work only after proving disjoint resources and acceptable foreground latency. Hold multi-adapter reservations together and in stable order. Recheck capacity and policy before execution. On pressure or device loss, stop new admissions and drain or checkpoint through supported operations.
5. Requalify after a driver/backend, device topology, model digest or critical context setting changes. Offer a smaller verified local profile or a verified CPU profile under explicit policy. A local failure never authorizes remote AI use.

## Verification matrix

| Scenario | Expected outcome | Current evidence |
|---|---|---|
| Empty inventory / telemetry failure | Distinct measured-empty and UNKNOWN results | Synthetic tests |
| Mixed vendors / duplicate names | Separate observations with unknown inference capability and capacity | Synthetic tests |
| Windows display discovery | Record the actual CIM observation, including virtual adapters or an empty result | CI job log |
| CPU-only workload, integrated/shared memory, discrete GPU, multi-GPU | Run admission and quality gates separately for each supported arrangement | NOT_RUN |
| Device removal, stale sample, backend change, foreground preemption | Invalidate affected leases and requalify before admission | NOT_RUN |
| RTX 3060 reference machine | Run the same workload and quality gates as on any other machine | NOT_RUN |

POC-04 and POC-10 remain open. T10/T120 keep the Hermes context requirement. T12/T124–T127/T140 require measured placement, context, quality and foreground behavior on each claimed supported profile. Hardware-specific thresholds cannot transfer between profiles. A Windows CI inventory result proves enumeration only.

Sources: [Microsoft display-controller schema](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-videocontroller), [DXGI budget fields](https://learn.microsoft.com/en-us/windows/win32/api/dxgi1_4/ns-dxgi1_4-dxgi_query_video_memory_info), [Ollama hardware support](https://docs.ollama.com/gpu).
