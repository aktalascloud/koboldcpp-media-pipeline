# KoboldCpp media pipeline · Dirty MOSS
[Русский](README.ru.md) · **[Windows kit](https://github.com/aktalascloud/koboldcpp-media-pipeline/releases/latest)** · [API / OWUI](docs/API.md) · [Models](docs/MODELS.md) · [Licenses](docs/LICENSES.md)

Portable photo/music wrapper for [our Haswell AVX2 / RX580 Polaris Vulkan KoboldCpp fork](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa) and [original KoboldCpp](https://github.com/LostRuins/koboldcpp). DirectML handles restoration/upscaling; Kobold remains the generator. AUTOMATIC1111 and OpenAI Images-compatible proxy APIs are preserved.

**Dirty MOSS Q8_0 · Euler/simple ·8 steps ·CFG1 ·eta0 ·shift5.** Static adapters: **DMD2 dynamic69 1.0 + Afterlight0.25 + Textslider0.25**; no trigger words or client LoRA tags. Normal/edit 736×1104; High 928×1392. Cache-DiT0.08/warmup4/Fn16/Bn2, FA on. Normal has no automatic SR; `enable_hr:true` requests ClearReality4x; High defaults to4x. YuNet960/GPEN20%/SFace0.97/Gater1x remain enabled. MusicMP3 is API-only; the photo model returns afterward.

## Saved examples
| Selected Euler + both0.25 | Night: alternate DPM/turbo-only | Watchmaker: alternate DPM/turbo-only |
|---|---|---|
|![Fullbody](examples/fullbody-native.png)|![Night](examples/night-native.png)|![Watchmaker](examples/watchmaker-native.png)|
|![Eyes](examples/fullbody-eyes.png)|![Eyes](examples/night-eyes.png)|![Eyes](examples/watchmaker-eyes.png)|

Raw Native outputs, not face-restored/upscaled results. Eye crops contain original pixels, without enlargement. [RGB provenance](examples/gallery.json). Clock markings, anatomy and tiny features can still contain artifacts.

## Measured speed
27 October 2026, XeonE5-2696v3/RX5802048SP8 GB; same 736×1104,8 steps,seed424242. EXE `6b815fe4ace2`, image `8276dcb69a15`. One pass per condition; **155.60s is Native only**, excluding load/faces/Gater/SR. Different cache skip counts explain much of the timing difference; this is not a compiler/patch speed claim.

| Condition | Native seconds | Cache skipped |
|---|---:|---:|
|turbo / DPM/sgm_uniform|163.06|1/8|
|turbo / Euler/simple|163.52|1/8|
|afterlight025 / Euler/simple|150.83|2/8|
|slider025 / Euler/simple|168.43|1/8|
|mix025 / DPM/sgm_uniform|178.87|1/8|
|mix025 / Euler/simple|155.60|2/8|

Dirty High and its complete4× API cycle were **not measured**. The [historical Refined4× image](examples/historical-refined-4x.png) and [161.96s public-cycle evidence](benchmarks/historical-refined.json) belong to the old model/settings; they are not Dirty results.

## Run
Extract the code kit, run `Setup.ps1 -MossSourceDirectory <your-originals>` once, then launch **Start.exe**. Setup requires the exact user-resized turbo file and gated text original; other pinned assets come from original distributors. Existing models are hash-checked and preserved. No main weights, LoRA binaries, keys, caches or logs are mirrored here. Optional startup uses one runtime and a separate visible Native window.

Normal/edit and High use the same selected adapters. High geometry is retained, not newly validated for this model. [Editing limitations](docs/EDITING.md) and [model-agnostic text-only reference synthesis](docs/REFERENCE-SYNTHESIS.md) remain explicit.
