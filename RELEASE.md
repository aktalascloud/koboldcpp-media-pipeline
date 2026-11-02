Normal photo and lossless4x delivery · 2026-11-02
- Pin accepted Core1.124.2 / cb260832 with gated Polaris SCALE/MOSS FFN views. Same current model weights and user settings;184 CPU/Vulkan cases and17 unprofiled generations retained identical RGB.
- Official stock→latest warm Normal: Native176.670→146.815s; faces/Gater pipeline184.423→154.698s. The incremental patch is0.47% Native /0.37% pipeline versus prior fork. [All first/repeated/return controls, SHA and limits](results/photo-latest.json).
- Real Normal + separate4x2944×4416 API checks passed without repeated restoration. Lossless PNG3 encoding1.566→1.052s, file+1.4%, exact RGB/text; overlapping SR HTTP ranges do not prove a whole-request gain.
- One locally built portable KoboldCpp.exe; original pinned runtime/model downloads reused. No weights/private runtime mirrored. Manual tests only; no new LLM/video benchmark. [Licenses](docs/LICENSES.md).
