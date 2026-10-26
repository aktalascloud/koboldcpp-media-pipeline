# Exact model setup
No main image/text/music weights are distributed in this repository or release. `models.json` pins exact sizes/SHA256. Existing mismatched files are preserved and rejected; user originals are never deleted.

## Required originals
Supply both files in `Setup.ps1 -MossSourceDirectory <folder>`:

| Role | Original | SHA256 |
|---|---|---|
| Refined image BF16 |`mossRefinedRealism_v108 steps_bf16.safetensors`,10164691056 bytes|`292f41c04bfb4be1eacfcd42eb6a0ee500757d25b6643cb7f6aa28bd4cf90fb3`|
| Artius W4A8 text |file3313824 from [author version3416029](https://civitai.com/models/3010191?modelVersionId=3416029),6857004728 bytes|`b0a6c1ab290b55c083fea294179c6c41b9027f645355e7eb63566dd1cb63efd1`|

**Refined source author URL/license metadata were not independently verified.** Obtain the original under its author's terms; Setup requires your exact local file instead of guessing a mirror or redistributing it. Its filename/hash identify the tested artifact. Main BF16 and converted Q8 are never uploaded here.

The exact gated text file requires your own Civitai access; Setup accepts it locally or uses process-only `CIVITAI_API_KEY` for the original endpoint. The key is never saved/printed and is stripped on cross-host redirects. Another HF text checkpoint is not silently substituted.

## Derived working outputs
- `MOSS/models/refined-realism-v10-q8_0.gguf`:5401122784 bytes, SHA256 `061903b58b6dfc6e317ba6fe5064c4a2cee94172f77d4d4cf9c1fff423c3c623`.
- `MOSS/models/text-q8_0.gguf`:10400747200 bytes, SHA256 `f3083eab75745e7d3e0cfc8184747d5e53ae4a23811096345d0e2b361c571bde`.

You may copy these exact verified files from your existing installation before Setup instead of reconverting. Otherwise the included streaming converter handles BF16 image tensors and the exact packed W4/ConvRot text source. GGUF headers/name/description are pinned too: hashes cover the entire file, not only weights. Q8 adds rounding; starting from another INT8 file does not promise faster inference in the same Q8 runtime.

Qwen3.5 official tokenizer, FLUX2 VAE, ClearReality FP32, GPEN and AceStep downloads are pinned in `models.json`. GPEN comes directly from its original FaceFusion distributor or `-GPENPath`, under Non-Commercial terms; not mirrored. ClearReality is an unmodified Apache2 FP32 ONNX download. Runtime/common asset URLs and hashes are in `release-assets.json`; unused Helaman/Torch/Z-Image paths from historic archives are not extracted. Keep enough space for originals, temporary conversion and output; roughly60 GB during a fresh setup.

Fresh-machine generation was not repeated for this release. The existing installation's real Normal 4× request and separate cold-start/API checks are recorded; installer traversal/resume/source-preservation and tiny BF16/INT8 conversions are checked offline.
