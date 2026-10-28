# KoboldCpp media pipeline · Ray MOSS
[Русский](README.ru.md) · **[Windows kit](https://github.com/aktalascloud/koboldcpp-media-pipeline/releases/latest)** · [API/OWUI](docs/API.md) · [Models](docs/MODELS.md) · [Licenses](docs/LICENSES.md)

Portable photo/music wrapper for [our Haswell AVX2 / RX580 Polaris KoboldCpp fork](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa) and [original KoboldCpp](https://github.com/LostRuins/koboldcpp). Kobold remains the generator; faces use CPU OpenVINO, restoration/SR use DirectML.

**Ray Artshoot Q8_0 + Afterlight0.25 · DPM++2M SDE/sgm_uniform · 8 steps · CFG1 · eta0 · shift5.** Ray is already SFT Turbo: no extra turbo adapter or trigger words. Cache-DiT0.08/warmup4/Fn16/Bn2; FA enabled; CPU text encoder20 threads.

Normal/edit **736×1104**, faces/Gater, no automatic SR. `enable_hr:true` adds ClearReality4×. High **928×1392**, same sampling, defaults to4×; selected Ray High generation is not measured. MP3 music loads on demand, then photo returns to GPU.

## Selected saved examples
| Fullbody | Night | Watchmaker |
|---|---|---|
|![Normal](examples/fullbody-processed.png)|![Night](examples/night-processed.png)|![Watchmaker](examples/watchmaker-processed.png)|
|![Eyes4x](examples/fullbody-eyes.png)|![Eyes4x](examples/night-eyes.png)|![Eyes4x](examples/watchmaker-eyes.png)|

| Exact Native source | Actual Normal4× API output, web preview |
|---|---|
|[![Native](examples/fullbody-native.png)](examples/fullbody-native.png)|[![4x](examples/fullbody-4x-preview.png)](examples/fullbody-4x.png)|

Fullbody4× is the actual public request; other scenes use the same post-chain on saved frames. Preview resizing is labeled; full PNGs/eye crops preserve original pixels. [RGB provenance](examples/gallery.json). Anatomy, irises, clocks and small writing can still contain artifacts.

## Measured time
**Actual Normal + faces/Gater/ClearReality4×: 175.14s**,2944×4416, one request without explicit mode/size. BaseAPI 163.081s; faces 1.359s; Gater 3.867s; SR 1.017s. Remaining time includes encoding/handoff/API overhead. Model resident before request; Normal restored afterward.

28 October2026, XeonE5-2696v3/RX5802048SP8GB, EXE `6c03b583f7a2`, image `dd02927547bc`. One public measurement; [exact scope and separate scene timings](benchmarks/results.json). Historical Dirty/Refined numbers are not new results. Enabled native compute ports have no isolated speed measurement; no compiler gain is claimed from these model changes.

## Run / layout
Run `Setup.ps1 -MossSourceDirectory <originals>` once, then **Start.exe**. Sources and SHA are pinned; the gated text original needs your access. Existing verified assets migrate instead of redownloading.

- `MODELS/`: image, text/tokenizer, VAE, LoRA and music weights.
- `DETAILERS/`: YuNet/GPEN/SFace and Gater.
- `UPSCALERS/`: ClearReality4×.
- `profiles/`, `tools/`, `runtime/`: current configuration/code and one Python runtime.

Dirty is an **optional backup**, not installed by default: `-IncludeDirtyBackup` requires its exact user-resized turbo original. No main weights, LoRA binaries, keys, caches or logs are mirrored. GPEN comes directly from its original distributor, Non-Commercial. [Editing contract](docs/EDITING.md) and [text-only reference synthesis](docs/REFERENCE-SYNTHESIS.md) are preserved.

## Music

**YuE2 Q8 + F16 VAE**, client-side NeoHorse helper, MP3 stereo. One measured32s request: **57.01s** including model handoff; photo resident again by61.07s. Russian short trial accepted by the user; long songs untested. [OWUI filter](docs/MUSIC.md), [Russian specification](docs/MUSIC.ru.md), [MP3 example](examples/yue2-russian-32s.mp3), [proof](benchmarks/music.json). Weights CC-BY-NC-4.0, original downloads only; ACE-Step removed.

## Video

[480p Native generation,720p enhancement and API](docs/VIDEO.md) · [Русская инструкция OWUI](docs/VIDEO.ru.md) · [Measured timings](benchmarks/video.json). Models download from their original distributors.

<!-- video-research -->

[Restorers, alternative VAEs and factory sampler comparisons](docs/VIDEO_RESEARCH.md). No candidate VAE is silently enabled; the selected fast Super-Tiny pipeline remains the default.
