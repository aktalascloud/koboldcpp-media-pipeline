# KoboldCpp portable media pipeline

**[Русская версия](README.ru.md)**

Portable Windows photo/music pipeline for **RX 580 Polaris (gfx803)** and Haswell/AVX2, using **[the optimized KoboldCpp CPU/Vulkan fork](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa)**. Kobold remains the model backend. The proxy adds automatic model switching, face refinement, image restoration and optional Helaman 4× upscaling through A1111/OpenAI-compatible routes.

**[Portable release assets](https://github.com/aktalascloud/koboldcpp-media-pipeline/releases/latest)** · [Original KoboldCpp](https://github.com/LostRuins/koboldcpp) · [API / OpenWebUI](docs/API.md) · [Licenses and model downloads](docs/LICENSES.md) · [Existing comparisons](examples/README.md) · [Measured timings](benchmarks/results.json)

## Selected results

Existing results from several benchmark scenes, selected after inspecting faces and eyes. No new image generation or retouching was performed. Click an image for its saved resolution.

### Other scenes from earlier tests

| Portrait in window light | Watchmaker at work | Tailoring studio |
|---|---|---|
|[![Window portrait](examples/portrait-window-helaman-2x.png)](examples/portrait-window-helaman-2x.png)|[![Watchmaker](examples/watchmaker-workbench-2x.png)](examples/watchmaker-workbench-2x.png)|[![Tailoring studio](examples/tailoring-studio-native.png)](examples/tailoring-studio-native.png)|
|1280×1728; historical Helaman FP32 DirectML **2×** test.|1280×1728; historical **2×** LoRA test with PhysioShade 0.15 / FlowDPO 0.35 / MaskedDPOFull 0.25.|544×816; **native** resolution test, Euler/beta, 8 steps, eta=0, with the selected three LoRAs.|
|![Portrait eyes](examples/portrait-window-helaman-2x-eyes.png)|![Hands and metal](examples/watchmaker-workbench-2x-hands.png)|![Studio portrait eyes](examples/tailoring-studio-native-eyes.png)|

These PNGs were recovered from saved tool previews of our earlier tests after the original benchmark folders had been cleaned. Their RGB pixels are preserved and metadata is stripped. They use different resolutions and processing stages: they are quality examples, not a controlled comparison of the current complete pipeline. Missing timings and unverified finishing stages are not inferred. [Per-image provenance](examples/historical-scenes.json).

### Matched full-body example: hair tied back, Helaman 4×

This is the retained preferred full-body reference. The **608×912** source already includes PhysioShade 0.15 + FlowDPO 0.35 + MaskedDPOFull 0.25, Euler/beta, 8 steps, eta=0, Cache-DiT 0.08, YuNet/GPEN/SFace and Gater Restore. Helaman outputs **2432×3648**, without a second face/restoration pass.

**Upscaling alone: 194.90 s** with exclusive VRAM, versus 516.15 s with photo weights still loaded. RGB pixels are identical between those two memory policies. Photo generation and the later photo-model reload are outside that upscaling time.

| Refined source: 608×912 | Helaman output: 2432×3648 |
|---|---|
|[![Preferred full-body source](examples/normal-608x912-final.png)](examples/normal-608x912-final.png)|[![Preferred full-body Helaman 4×](examples/resident-normal-4x.png)](examples/resident-normal-4x.png)|
|![Source face](examples/sr-input-face.png)|![Upscaled face](examples/helaman-4x-face.png)|
|![Source eyes](examples/sr-input-eyes.png)|![Upscaled eyes](examples/helaman-4x-eyes.png)|

The current Normal default remains **592×896**, measured at **145.34 s first request / 140.09 s repeat**, without SR. The 608×912 image above is a separately labeled saved reference. The loose-hair clock portrait is excluded from this selected gallery.

All crops use saved pixels without resampling. The 4× source pair is verified by RGB hash. A baseline clock-hand defect remains in the full-body scene; perfect geometry is not claimed. [Historical controls and provenance](examples/README.md).


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
