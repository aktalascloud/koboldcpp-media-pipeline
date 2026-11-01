Media reliability and optional audio-driven lip-sync
- Fix Pro VAE monitoring after portable path relocation and a reproduced FFmpeg dual-output audio hang. Preserve idempotent generation receipts and explicit failure stages.
- Real RIFE48FPS default/60 optional; stored MP4 import/interpolation, explicit lip-sync targets/voices and exact-WAV reuse.15/30s is client orchestration; tested Native clip73frames.
- Measured: I2V73 full720p/face/RIFE48 pipeline583.63s; stored60FPS lip-sync29.12s; three-track mix57.37s with identical video. No new LLM token claim. [Proof](results/measurements.json).
- [Build](docs/BUILD.md) · [API](docs/API.md) · [Licenses](docs/LICENSES.md). Models, LoRA weights, private runtime and credentials are not mirrored. Optional Wav2Lip/GPEN retain non-commercial terms.
