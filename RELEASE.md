MOSS image-operation contract, schema2. Existing Refined/DPM/SGM/ClearReality settings are preserved.

- New `GET /v1/images/capabilities`: one target, zero references, no instruction-edit or masks.
- `/v1/images/edits` now rejects unsupported instruction edits with422 and no PNG/inference. Redraw requires explicit `operation:img2img`; a model alias cannot silently select an operation.
- JSON/multipart/A1111 redraws share source/aspect/strength validation. Actual checkpoint is reported; unavailable models, multiple images, references and unsupported parameters are rejected instead of ignored.
- Final faces/Gater retained; edits do not auto-upscale. Existing Normal `enable_hr:true`4x and music remain intact.
- Real small320x256 redraws and negative HTTP regressions verified. These do not prove semantic recoloring. Saved Normal4x161.96s is the earlier pre-contract-change reference on the same native EXE/profile, not a new full-resolution measurement for this release.

Extract **media-pipeline-code.zip**, run **Setup.ps1 once** for a new installation, then **Start.exe directly**. Main weights are not included; exact user-supplied Refined source and gated text source/verified GGUF are required. Existing runtime assets are pinned and reused. No keys/private state are shipped; GPEN is downloaded from its original distributor.

[Editing/capabilities and OWUI rules](https://github.com/aktalascloud/koboldcpp-media-pipeline/blob/main/docs/EDITING.md) · [Evidence](https://github.com/aktalascloud/koboldcpp-media-pipeline/blob/main/benchmarks/edit-contract.json)
