# Exact models and adapters
No main weights or LoRA binaries are distributed. Original author terms apply; `models.json` pins size/SHA256. User originals and existing mismatched assets are preserved.

## Setup originals
Use `Setup.ps1 -MossSourceDirectory <folder>`. Supply the exact user-resized turbo and the gated Artius text original. Dirty INT8 and quality LoRA can also be imported from that folder, otherwise Setup downloads from the original author endpoint. A different turbo rank/file is not silently substituted.

|Asset|Source / import|SHA256|
|---|---|---|
|`dirtyMoss_int8.safetensors`|[image](https://civitai.com/models/3015644?modelVersionId=3423156) · aliases `dirtyMoss_3317587.safetensors, dirtyMoss_int8.safetensors`|`dd17ac4099151719ffd233d83d3f6ab376080fa93d91326ab033242a2fa1e43e`|
|`txt-artiusMoss_v10_3313824.safetensors`|[text](https://civitai.com/models/3010191?modelVersionId=3416029) · aliases `artiusMoss_v10_3313824.safetensors, txt-artiusMoss_v10_3313824.safetensors`|`b0a6c1ab290b55c083fea294179c6c41b9027f645355e7eb63566dd1cb63efd1`|
|`turbo-dmd2-dynamic69.safetensors`|[adapter](https://civitai.com/models/3006599?modelVersionId=3420002) · aliases `lodestones-8-steps-dmd2-lora_resized_from_128_to_dynamic_69.safetensors`|`d869785c75a20a409f1b590d4ad3a825b542a1fbb9f21589e5ad5e46e62c6910`|
|`afterlight-v1.safetensors`|[adapter](https://civitai.com/models/3016917?modelVersionId=3424873) · aliases `Moss-Afterlight-V1.safetensors`|`57d2a400af32a0afd9cd065c43ebeb6a0e44b153abaef0171ce6891b6b057d13`|
|`quality-textslider-r16.safetensors`|[adapter](https://civitai.com/models/3008688?modelVersionId=3414043) · aliases `moss_anima_pure_text_slider_rank16.safetensors`|`29d7b624a374104a79cbe5d3d07127caf6f175e5a530baa095a7bdf6a887ccc8`|

The turbo is the tested dynamic69 derivative (ranks58–112), not the full rank128 author download. Place the exact existing file in the originals folder; its hash is mandatory. This project does not redistribute or claim a license for that derivative. Quality-adapter cards declare no mandatory trigger.

Dirty INT8 ConvRot is decoded with inverse rotation/per-row scales, then requantized to standard Q8. Exact GGUF name/description are pinned for byte-identical installation. This is not bit-identical to author Comfy INT8 inference. The author25-step CFG2/SLG/hires workflow is not reproduced by the selected8-step turbo adaptation.

## Working outputs
- `MOSS/models/dirty-moss-q8_0.gguf`: 5401126112bytes, SHA256 `8276dcb69a1550924b44b35ff7d0264357196349ae0d7d74edba88ca91f0653b`.
- `MOSS/models/text-q8_0.gguf`: 10400747200bytes, SHA256 `f3083eab75745e7d3e0cfc8184747d5e53ae4a23811096345d0e2b361c571bde`.
- `MOSS/models/vae.fp32.safetensors`: 249521372bytes, SHA256 `c3bdf94dc67ec69b30ea9fe1fa8340085679cae64d019f7c7e4a9921f1a7f17a`.
- `MOSS/models/tokenizer.json`: 12807982bytes, SHA256 `5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42`.

Existing exact GGUF files may be copied before Setup. The text original needs your Civitai access; no alternative encoder is substituted. GPEN comes directly from its original distributor under Non-Commercial terms, not this release. ClearReality FP32 remains Apache2. See [licenses](LICENSES.md). Setup/converter guards are checked offline; fresh-machine generation and selected Dirty High/full4x are not claimed tested.
