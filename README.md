# KoboldCpp media pipeline
[Русский](README.ru.md) · [Release](https://github.com/aktalascloud/koboldcpp-media-pipeline/releases/latest) · [Install/build](docs/BUILD.md) · [API / OWUI](docs/API.md) · [Licenses](docs/LICENSES.md)

Portable Windows media around [our Haswell/AVX2 RX580Polaris/gfx803 fork](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa) of [original KoboldCpp](https://github.com/LostRuins/koboldcpp). Run **Start.exe → KoboldCpp.exe**. Models switch exclusively; image stays GPU-resident when idle. Setup.ps1 is initial installation/update, not the launcher. No main weights are mirrored.

- Images: RayQ8/Afterlight.25/RealismEnhancer1,Euler/simple8,eta0,CacheDiT.08. Normal736×1104 noautoSR; High928×1392 defaultClear4x, new High mix unmeasured. YuNet/GPEN20/SFace.97/Gater beforeSR, no repeat afterwards.
- Music: YuE2MP3. SFX: SA3CPU WAV/MP3,0.25–60s. Speech/helper/STT: configurable provider, RU/EN explicit voices.
- Video: Wan5BTurbo/fullencoder/ProFP32/Euler-beta4,WG512,threshold576,Clear720/faces/optionalRIFE. NoTiny/Helaman. Timed audio is separate generation/mixing, not joint AV/lip-sync. Native call<=121frames/5.04s;20s default/60s maximum is the OWUI orchestration spec.

## Latest saved results
| Saved test | Actual wall time | Scope |
|---|---:|---|
| PhotoNormal | 163.85s |29Oct, ff7d4d0b, one API |
| Separate photo4x | 6.04s |saved PNG, separate API |
| Video3.04s | 552.57s |30Oct,0986410a,I2V/Pro/Clear720/faces/all3audio |
| Audio revision | 57.96s |73RGB frames unchanged, no video rerun |
| Music32sMP3 | 57.01s |28Oct,6c03b583, photo return61.07s |
| SFX2sWAV /6sMP3 |10.57s /17.17s |30Oct CPU, photo stayed resident |

Settings/ranges/dates/SHA: [one measurement file](results/measurements.json). **Current native1.124.1/ed587d0b has startup checks only.** Video samples used a private user adapter, not enabled/distributed in this kit. Historical timings are not a new speed claim.

| Actual Normal | Actual4x, full lossless image linked |
|---|---|
|![Normal](results/photo-normal.png)|[![4x](results/photo-preview.webp)](results/photo-4x.webp)|
![Unscaled4x eye pixels](results/photo-eyes.png)

Only necessary code/config/licenses and current results. Models/detailers/upscalers under MODELS, one runtime; all evidence under results. [Local-model build rules](AGENTS.md). Full owner-local EXE is built locally, not mirrored without runtime redistribution review. Fresh-machine full inference has not been tested.
