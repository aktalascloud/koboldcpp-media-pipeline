# KoboldCpp portable media pipeline

Portable Windows photo/music pipeline for **RX 580 Polaris (gfx803)** and Haswell/AVX2, using **[the optimized KoboldCpp CPU/Vulkan fork](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa)**. Kobold remains the model backend. The proxy adds automatic model switching, face refinement, image restoration and optional Helaman 4× upscaling through A1111/OpenAI-compatible routes.

**[Portable release assets](https://github.com/aktalascloud/koboldcpp-media-pipeline/releases)** · [API / OpenWebUI](docs/API.md) · [Licenses and model downloads](docs/LICENSES.md) · [Existing comparisons](examples/README.md) · [Measured timings](benchmarks/results.json)

## Exact chosen chain

1. Photo profile resident on Vulkan between requests. Moody Pro Mix, protected Qwen3 text encoder on CPU20, SD Q4 runtime quantization; base weights are not redistributed.
2. PhysioShade0.15 + FlowDPO0.35 + MaskedDPOFull0.25. Prompt prefix **physioshade** is inserted once. No documented special Flow/Masked trigger. Do not load the LoRAs a second time in the request.
3. Euler / beta,8 steps, eta0, CFG1, flow shift3, clip skip−1, Cache-DiT threshold0.08/warmup4/Fn16/Bn2. SD flash attention disabled.
4. YuNet960, score0.82, GPEN512 on OpenVINO CPU blended20%, SFace minimum0.97, at most2 faces. Face-size thresholds scale with image area (Normal592×896:31–125).
5. GaterV3 Restore1x, FP32 DirectML, strength1, after faces. No sharpen model.
6. Normal/edit **592×896**, no automatic SR. High **1152×768** (portrait768×1152), automatic native **Helaman ATD4x**. No downsize to 2x and no repeat face/Gater pass after SR.

Standalone SR applies faces/Gater before Helaman unless valid pixel-bound PNG markers prove prior processing. The supervisor unloads only its own idle Kobold Native before SR, gives SR exclusive VRAM, then restores photo asynchronously. Never keep photo weights and Helaman co-resident on this8 GB card.

Music uses the same Kobold EXE and the original AceStep planner; its separate profile loads only on API demand, outputs stereo MP3, then restores photo. The30 s prepare-idle policy is retained. Video is deferred and its weights/runtime are excluded from this minimal kit.

## Existing measured results

Xeon E5-2696v3 / RX5802048SP8 GB / Windows. No new images/audio were generated to publish this project.

| Scope | Before | After | Notes |
|---|---:|---:|---|
| Same576×864,3 LoRA+faces+Gater,noSR |stock163.15 s|new cold 138.35 s / warm 131.83 s|Previous optimized136.02 s; the new cold run is slower than that prior optimized run.|
| Current Normal592×896,all above,noSR |first 145.34 s|repeat 140.09 s|+6.584%pixels vs576×864.|
| Normal warm stages |Native135.510 s|faces1.018 s + Gater2.836 s|Remaining time is transport/encoding; edits were not timed again.|
| Helaman608×912 to 2432×3648 |co-resident516.15 s|exclusive194.90 s|2.648×; RGB byte-identical. Photo reload after the API response is additional.|
| Music prepare/lifecycle |not a matched speed comparison|23.61 s|Real prepare passed; audio was not regenerated.|

Exclusive SR used about7.41 GB dedicated and0.269 GB shared/upload memory, versus multi-GB shared eviction in the bad co-resident case. Small upload/shared buffers are not proof of disk paging. Full new High+4x was not repeated after the residency fix; no fabricated High timing or universal OOM guarantee. The selected Euler image still has a baseline clock-hand defect: refinement does not guarantee correct geometry.

## Install

Extract `media-pipeline-code.zip` into a new folder and run `Setup.ps1` once. It downloads the pinned runtime/model components from the base release and the direct-launch core EXE package. Large Moody/Qwen/AceStep models are downloaded from their original hosts; you can also supply the exact files locally. Model licenses still apply. File hashes and profile manifests are verified during setup.

After installation, launch **Start.exe directly**. Daily use requires no PowerShell launcher. `Start.exe --check` performs a preflight check. To opt into Windows startup, run `runtime/python/python.exe -I -B tools/Launch.py --register-startup`; otherwise the registry is unchanged. Kobold opens in its own visible console.

The public kit defaults to loopback API5001, private Native5003; no credentials or private network addresses. To serve another machine, deliberately configure the proxy host/firewall and protect network access. Keep private Native on loopback.

Code: AGPL-3.0; third-party runtimes/models retain their original terms. GPEN is a separate optional **Non-Commercial** weight asset, not part of the AGPL/Apache/CC-BY grant; see its notice before use. [Component/license details](docs/LICENSES.md).
