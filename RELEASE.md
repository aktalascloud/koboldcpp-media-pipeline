Model-agnostic reference synthesis on the existing MOSS generator. No new model weights.

- `GET /v1/images/synthesis-schema` returns a universal vision-analysis/caption template.
- `POST /v1/images/synthesize` accepts2–4 client source analyses with explicit base/reference roles, hashes, user request and final caption. Any caller-selected vision provider can prepare them; no provider/model is fixed.
- Included stdlib client helper takes a sync/async vision callback, makes one analysis call and preserves trusted IDs/roles/hashes.
- Conditioning is explicitly TEXT ONLY: MOSS does not see raw references, exact face identity and pixel preservation are not guaranteed. Unsupported instruction-edit still returns422; no automatic fallback.
- Actual small MOSS caption-handoff test passed at320x480 in23.92s, using truthful manual source descriptions. This does not claim an external vision model was tested.

Existing Refined/DPM/SGM/Cache-DiT/face/Gater/ClearReality4x and music settings are preserved. Runtime/postprocessor assets are pinned downloads. Main weights and credentials are not distributed. Existing Normal4x timings are historical references, not fresh full-resolution measurements for this API release.

[API and OWUI callback](https://github.com/aktalascloud/koboldcpp-media-pipeline/blob/main/docs/REFERENCE-SYNTHESIS.md)
