# Consolidation and integration decisions

## Source priority

The current working-folder export is the authoritative application snapshot. The original input archive fills missing resources and the available updated notebook supplies kernel-only model/synthesis configuration. Overlapping old backend and dashboard variants are not copied over newer working files. Hashes and per-file origins are recorded in MERGE_MAP.json.

## Applied source retained

The current booking guard, structured slot parser, geocoder, independent endpoint forecast adapter, confirmation controller, booking tools, friendly weather, native pronunciation helper, customer-care engine/API/context and dashboard assets are included as ordinary source files. Their existing version-guarded startup hooks remain in place. Original installer notebooks, historical backup copies, notebook outputs, private database, logs and Python caches are excluded.

## Missing resources added

- English and Tamil reference WAV files from the original input package.
- The supplied view-only upcoming-booking JavaScript, and its matching scheduled/requested driver-list query. Driver assignment, vehicle filters and guarded acceptance remain in the existing backend.
- A normal gateway source file with website/AI routes separated correctly, forecast speech routed to the voice service and proxy-environment inheritance disabled for local upstream HTTP.
- One ordered model, speech and service runtime from the available updated notebook.

## Targeted integration adjustments

- Initialize the base database schema before weather hooks migrate rides. A fresh standalone website otherwise lacked pickup_time and its driver listing failed. The local HTTP fixture verifies the corrected startup.
- Persist the existing in-memory scheduled-cancellation status addition in the canonical legacy voice socket source.
- Recreate runtime-only wordwise speech and stable weather/closing profiles once, bind the exported speech-quality helper, and preserve source-owned weather/summary functions. Shared closure registries are connected explicitly; no old file installers are replayed.
- Retain the requested Vandalur/Vandaloor and Celsius speech replacements without changing browser transcript text.
- Register forecast speech only after the shared HTTPS origin is known.
- Update the single obsolete core test that required weather to be hidden from the transcript; the current requirement explicitly asks for the complete advisory to be printed as well as spoken. The updated assertion checks equality of the customer-facing spoken/display text and preservation of both endpoint probabilities.

## Six startup stages

1. Secrets, references and pinned DhVaani model loading.
2. Shared normalization, semantic/entity-aware preparation, reference caches and scheduler.
3. Qwen, original TTS adapter, current voice bridge and grounded extraction fallback.
4. Direct binding of existing weather/booking modules and runtime speech profiles.
5. Progressive forecast speech helpers and common pronunciation rules.
6. Voice, gateway, tunnel and website startup, forecast endpoint registration and health checks.

## Validation boundary

The directory now starts from applied source, rather than running a chain of historical source replacements. Necessary runtime-only speech adapters remain. A full GPU startup and browser demonstration have not been executed during packaging. The supplied legacy full-stack test failures are documented rather than presented as passing results. The complete historical ASR/TTS evaluation notebooks were not part of the current working export; no benchmark outputs are invented.
