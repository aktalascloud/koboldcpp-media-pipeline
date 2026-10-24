# Exact models and first installation

No main MOSS, Qwen or AceStep weights are included in Git or our releases. `models.json` pins sizes/SHA256, sources and local generated outputs. Third-party licenses are separate from the wrapper license.

## MOSS
The measured originals were Artius Moss v1.0 from the author's [model version3416029](https://civitai.com/models/3010191?modelVersionId=3416029):

| Role | Exact source | Bytes | SHA256 |
|---|---|---:|---|
| Image | file3309287 / HF `Artius_Moss_int8_hq_v1.safetensors` |7494295376|`187a5c86c6fea9497bf16d43c5d780ebd46fb52f17a4a8faa2bd553218b0344b`|
| W4A8 text | file3313824 |6857004728|`b0a6c1ab290b55c083fea294179c6c41b9027f645355e7eb63566dd1cb63efd1`|
| VAE | file3311372 / HF `moss_image_vae.safetensors` |249521372|`c3bdf94dc67ec69b30ea9fe1fa8340085679cae64d019f7c7e4a9921f1a7f17a`|

Image/VAE use SHA-matched pinned files in [hfmaster/artius-moss](https://huggingface.co/hfmaster/artius-moss/tree/d75d8f6bcb2423b21d42631751d39467fadfaba1). The current HF text file has a different SHA and is deliberately not substituted. The exact W4 encoder currently returns401 without the user's own Civitai access. No account credentials are provided by this project.

Download that encoder using your account and run `Setup.ps1 -MossSourceDirectory <folder>`. Known browser filenames and arbitrary `.safetensors` names are accepted only when exact size and SHA match. A process-only `CIVITAI_API_KEY` is another option; it is read from the environment, never saved/logged, and removed on cross-host redirects. The same large-model file is never obtained through an unrelated mirror.

Setup uses the bundled NumPy and MIT GGUF subset to decode the author's regular ConvRot/packed W4A8 format into standard Q8_0. Source imports use a temporary hard link when possible; your external originals remain untouched. Setup's verified temporary download/link is removed after the generated model fingerprint matches. Failed/incomplete downloads remain inspectable/resumable. Existing mismatched target files are preserved instead of overwritten.

| Generated local file | Bytes | SHA256 |
|---|---:|---|
|`MOSS/models/image-q8_0.gguf`|5401115744|`8a3ed10d3e568ce01860fd9fcecd3478b9a50df5d2a780c562a01dcd84b765c4`|
|`MOSS/models/text-q8_0.gguf`|10400747200|`f3083eab75745e7d3e0cfc8184747d5e53ae4a23811096345d0e2b361c571bde`|

Q8 adds rounding; original activation-INT8 math and author TemporalScoreRescaling are not reproduced. The author's restrictions still apply to weights. Converted weights are not distributed or relicensed here. The official Qwen3.5 tokenizer is a separate pinned download.

Initial download/conversion can require roughly60GB free including temporary sources and music. Setup never starts inference or modifies startup/driver settings. `-SkipModelDownloads` prepares only infrastructure and reports missing models; it is not a ready-to-generate installation. `Start.exe --check` validates the completed bundle. Copying the completed folder gives one portable runtime; re-register startup on a different machine if wanted.

## Runtime and postprocessing
The installer reuses hash-pinned release assets. Only runtime directories and currently used YuNet/SFace/Gater/ATD checkpoints are extracted. Old Z-Image LoRAs and tokenizer resources in the historic base archive are not installed. Native EXE and its original license files come from the pinned optimized core release.

GPEN is downloaded from the original [FaceFusion asset](https://github.com/facefusion/facefusion-assets/releases/tag/models-3.0.0) or supplied with `-GPENPath`. Non-Commercial classification and unresolved original redistribution scope are documented; the new code package does not mirror it. See [licenses](LICENSES.md).

AceStep music files use the pinned [KoboldCpp music HF repository](https://huggingface.co/koboldcpp/music), without changes to the measured MP3/on-demand model-switching policy.