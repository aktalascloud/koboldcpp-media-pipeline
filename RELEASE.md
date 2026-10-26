Refined Realism photo/music pipeline for Windows · Haswell AVX2 · RX580 Polaris/gfx803, 8 GB.

- Selected **DPM++ 2M SDE / sgm_uniform,eta0,8 steps,Cache-DiT0.08**.
- **Normal 736×1104 + faces/Gater + ClearReality4×: 161.96 s**, one complete public API request,2944×4416. Model resident; PNG/HTTP included. High 928×1392 profile retained, **Refined High timing unmeasured**.
- `enable_hr:true` now works for Normal proxy4×; no native hires/img2img pass. Helaman and repeated faces after SR removed. Music MP3 and visible Native startup preserved.
- Saved three-scene gallery and scalar timing/cache evidence. No new inference for publication; no claim DPM denoising beats Euler/simple.

Extract **media-pipeline-code.zip**, run **Setup.ps1 once**, then launch **Start.exe directly**. Requires exact user-supplied Refined BF16 plus gated Artius text original, or matching derived GGUF. No main weights in Git/releases. Runtime/common components are hash-pinned reuse; ClearReality comes from its Apache2 original, GPEN from its Non-Commercial original distributor.

[Setup/models](https://github.com/aktalascloud/koboldcpp-media-pipeline/blob/main/docs/MODELS.md) · [OWUI presets](https://github.com/aktalascloud/koboldcpp-media-pipeline/blob/main/docs/API.md) · [Optimized native fork](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa)
