Unified portable media update · 2026-11-02
- Pin the accepted native 1.124.2 / 6d2fedf core: YuE2 VRAM lifetime fixes, SheetSage2 engine support, WebP input and reasoning-budget grammar repair. Existing media models/settings are retained.
- One locally built KoboldCpp.exe, one runtime, unified demand-loaded photo/audio/video/effects API. Preserve resident idle photo, exclusive model ownership, generation receipts and optional explicit lip-sync.
- Source/hash/startup/visible-window/GET checks only; no new inference or speed benchmark. All saved timings retain their dates and executable SHA. [Proof](results/measurements.json).
- [Build](docs/BUILD.md) · [API](docs/API.md) · [Licenses](docs/LICENSES.md). Models, LoRA weights, private runtime and credentials are not mirrored. Optional Wav2Lip/GPEN retain non-commercial terms.
