# KoboldCpp portable media pipeline

Windows photo/music integration for **[the optimized KoboldCpp CPU/Vulkan fork](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa)**. Kobold remains the actual model backend. This proxy adds automatic model switching, face refinement, whole-image restoration and optional Helaman4x upscaling through A1111/OpenAI-compatible routes.

**[Portable release assets](https://github.com/aktalascloud/koboldcpp-media-pipeline/releases)** · [API / OpenWebUI](docs/API.md) · [Licenses and model downloads](docs/LICENSES.md) · [Existing comparisons](examples/README.md) · [Measured timings](benchmarks/results.json)

## Exact chosen chain

1. Photo profile resident on Vulkan between requests. Moody Pro Mix, protected Qwen3 text encoder on CPU20, SD Q4 runtime quantization; base weights are not redistributed.
2. PhysioShade0.15 + FlowDPO0.35 + MaskedDPOFull0.25. Prompt prefix **physioshade** is inserted once. No documented special Flow/Masked trigger. Do not load the LoRAs a second time in the request.
3. Euler / beta,8 steps, eta0, CFG1, flow shift3, clip skip−1, Cache-DiT threshold0.08/warmup4/Fn16/Bn2. SD flash attention disabled.
4. YuNet960, score0.82, GPEN512 on OpenVINO CPU blended20%, SFace minimum0.97, at most2 faces. Face-size thresholds scale with image area (Normal592×896:31–125).
5. GaterV3 Restore1x, FP32 DirectML, strength1, after faces. No sharpen model.
6. Normal/edit **592×896**, no automatic SR. High **1152×768** (portrait768×1152), automatic native **Helaman ATD4x**. No downsize to2x and no repeat face/Gater pass after SR.

Standalone SR applies faces/Gater before Helaman unless valid pixel-bound PNG markers prove prior processing. The supervisor unloads only its own idle Kobold Native before SR, gives SR exclusive VRAM, then restores photo asynchronously. Never keep photo weights and Helaman co-resident on this8GB card.

Music uses the same Kobold EXE and the original AceStep planner; its separate profile loads only on API demand, outputs stereo MP3, then restores photo. The30s prepare-idle policy is retained. Video is deferred and its weights/runtime are excluded from this minimal kit.

## Existing measured results

Xeon E5-2696v3 / RX5802048SP8GB / Windows. No new images/audio were generated to publish this project.

| Scope | Before | After | Notes |
|---|---:|---:|---|
| Same576×864,3LoRA+faces+Gater,noSR |stock163.15s|new cold138.35s / warm131.83s|Previous optimized136.02s; the new cold run is slower than that prior optimized run.|
| Current Normal592×896,all above,noSR |first145.34s|repeat140.09s|+6.584%pixels vs576×864.|
| Normal warm stages |Native135.510s|faces1.018s + Gater2.836s|Remaining time is transport/encoding; edits were not timed again.|
| Helaman608×912 to2432×3648 |co-resident516.15s|exclusive194.90s|2.648×; RGB byte-identical. Photo reload after the API response is additional.|
| Music prepare/lifecycle |not a matched speed comparison|23.61s|Real prepare passed; audio was not regenerated.|

Exclusive SR used about7.41GB dedicated and0.269GB shared/upload memory, versus multi-GB shared eviction in the bad co-resident case. Small upload/shared buffers are not proof of disk paging. Full new High+4x was not repeated after the residency fix; no fabricated High timing or universal OOM guarantee. The selected Euler image still has a baseline clock-hand defect: refinement does not guarantee correct geometry.

## Install

Extract the code and Windows runtime assets into one folder, run `Setup.ps1`, obtain the listed models under their own licenses, then `Start.exe --check` and `Start.exe`. Large Moody/Qwen and restricted models are downloaded or supplied locally; never embedded in Git. `Setup.ps1` verifies expected file hashes and regenerates installation-specific profile hashes/manifests. Use `runtime/python/python.exe -I -B tools/Launch.py --register-startup` to opt into Windows startup; otherwise no registry change. Kobold opens in its own visible console.

The public kit defaults to loopback API5001, private Native5003; no credentials or private network addresses. To serve another machine, deliberately configure the proxy host/firewall and protect network access. Keep private Native on loopback.

Code: AGPL-3.0; third-party runtimes/models retain their original terms. GPEN is a separate optional **Non-Commercial** weight asset, not part of the AGPL/Apache/CC-BY grant; see its notice before use. [Component/license details](docs/LICENSES.md).
