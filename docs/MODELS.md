# Exact models and original-file import
No main/LoRA weights are redistributed. `models.json` pins sizes/SHA256 and original endpoints. `Setup.ps1 -MossSourceDirectory <folder>` imports originals without altering them. The exact gated text file needs your access; no substitute encoder.

|Role|Original source/import|SHA256|
|---|---|---|
|`image`|[rayMossArtshoot_sftTurboV1.safetensors](https://civitai.com/models/3018302?modelVersionId=3426693)|`411f33aadfa3b6e8fd3e99ef6cd076b28a86fca4e92cc168b32f0d41b524904a`|
|`text`|[txt-artiusMoss_v10_3313824.safetensors](https://civitai.com/models/3010191?modelVersionId=3416029)|`b0a6c1ab290b55c083fea294179c6c41b9027f645355e7eb63566dd1cb63efd1`|
|`Afterlight`|[afterlight-v1.safetensors](https://civitai.com/models/3016917?modelVersionId=3424873)|`57d2a400af32a0afd9cd065c43ebeb6a0e44b153abaef0171ce6891b6b057d13`|

Ray is already SFT Turbo. The selected8-step DPM/sgm_uniform + Afterlight0.25 is a Kobold adaptation; author12-step Heun++2/linear_quadratic/SLG is not claimed reproduced. The tested Heun/custom8-point curve was slower and not selected.

Conversion reverses INT8 ConvRot/scales and writes Q8. Names/descriptions/writer headers are pinned; full GGUF hashes are verified. Exact compatible image/text GGUF files may be copied before Setup instead of reconversion. Q8 adds rounding; this is not bit-identical to original Comfy INT8 inference.

Dirty is optional: `Setup.ps1 -IncludeDirtyBackup -MossSourceDirectory <folder>`. See optional_dirty_backup in models.json. Its dynamic69 turbo is user-supplied, not the original full-rank author download; no replacement is silently accepted. The local workspace retains Dirty; fresh kits install only Ray by default.

MODELS contains weights; DETAILERS faces/Gater; UPSCALERS ClearReality. Verified legacy assets migrate; unknown/mismatched files are preserved. GPEN downloads directly from its original FaceFusion distributor, Non-Commercial; ClearReality is Apache2 FP32. [Licenses](LICENSES.md). One runtime; runtime/native downloads remain SHA-pinned.
