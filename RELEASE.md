Haswell and Polaris update · 2026-11-11

- Official `f49df57b4a82f6d641c419c7fadc9e4b896f6781`. Native SHA-256 `33615ff0474faa097deb188a4f326247f6f8ce99fd634da720b9573728c93a6e`. Haswell AVX2, LTO, 72 ordered local patches.
- ABDM Normal plus separate 4× phase sum 154.085 → 154.636 s versus the prior installed Native. All tested RGB outputs match. [Repeats and settings fingerprints](results/performance-2026-11-11-abdm.json).
- AVX2 state-row scheduling and single-pass Scale. CLIP allocation failures and graph metadata allocation. [Operation results](results/operations-2026-11-11.json) · [PR decisions](results/pr-review-2026-11-11.json).

[Native patch catalog](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa/tree/concedo_experimental/performance/patches/series) · [Licenses](docs/LICENSES.md).

The installer uses the verified October month-end FFmpeg archive. [Archive and codec checks](results/ffmpeg-install-2026-11-11.json).
