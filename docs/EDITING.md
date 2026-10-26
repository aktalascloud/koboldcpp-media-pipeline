# MOSS image-operation contract, schema2

Discover capabilities with `GET /v1/images/capabilities` (alias `/api/extra/image-capabilities`). Capabilities describe this installed checkpoint/backend, not every future MOSS model.

| Operation | Current support |
|---|---|
| Text-to-image | Yes; one output |
| img2img | Whole-frame redraw from a descriptive caption; one target |
| Instruction-edit, such as “only recolor this square” | **No: HTTP422** |
| Reference-guided or multiple-image editing | **No: target max1, references max0** |
| Masks / inpainting | **No: HTTP422** |
| Upscale | Separate4× API; image edits do not auto-upscale |

The installed Refined checkpoint is not an instruction-edit-trained model. A successful img2img PNG does not prove a requested color/object/identity change. The server reports `semantic_success_evaluated:false`; clients must not present it as successful instruction-following.

## Explicit redraw

`POST /v1/images/edits`, JSON:

```json
{
  "operation": "img2img",
  "model": "kobold-moss-img2img",
  "target_image": "BASE64_OR_DATA_URI",
  "reference_images": [],
  "prompt": "A complete descriptive caption of the desired whole image.",
  "denoising_strength": 0.6,
  "steps": 8,
  "seed": 424242,
  "response_format": "b64_json"
}
```

`target_image` is the editable source. `image`/single-element `image[]` are legacy target aliases, not references. Do not send multiple target aliases together. `reference_images` is a separate role and currently must be empty. URLs/file paths are not fetched. Multipart supports one file named `target_image` or `image`; text fields carry operation/model/prompt/strength. **The model alias does not select the operation: operation=img2img is mandatory on this endpoint.** Clients unable to send it must use the explicitly named A1111 img2img endpoint or report unsupported editing.

The response identifies the resolved checkpoint and `operation:img2img`, `semantics:whole_frame_redraw`, `processing_success:true`, `semantic_success_evaluated:false`. Model aliases verify the configured server model; they do not load another checkpoint. Unknown models, including unavailable GPT/DALL-E names, return422 rather than being ignored.

For A1111, `POST /sdapi/v1/img2img` with exactly one `init_images` entry already means whole-frame redraw. The same upload/strength/aspect/model/reference validation applies. Strength0.05–1, steps1–9; source aspect preserved with uniform fitting/edge padding. MOSS sampling/profile stays server-managed. Img2img uses no Cache-DiT because the partial schedule is separate from the measured txt2img cache profile. Final YuNet/GPEN/SFace/Gater processing remains enabled where applicable; use standalone SR afterward if wanted.

## Unsupported instruction

Without explicit redraw intent, `/v1/images/edits` means instruction-edit and returns:

```json
{
  "error": {
    "type": "invalid_request_error",
    "param": "operation",
    "code": "instruction_edit_unsupported",
    "message": "This checkpoint has no instruction-edit mode. Explicit img2img is whole-frame redraw from a descriptive caption, not a precise editing command.",
    "capabilities_url": "/v1/images/capabilities",
    "supported_operations": ["img2img"]
  }
}
```

Reference inputs return `reference_images_unsupported`; multiple targets return `multiple_images_unsupported`; masks return `mask_unsupported`; unavailable models return `unsupported_image_model`. Unsupported requests have no PNG/data and do not start inference.

## OWUI/filter requirements

1. Read capabilities; absence/404 is unknown support, not permission to assume instruction-edit.
2. Bind the selected source to target_image. Keep references in their own role; never silently discard references or use the first uploaded image as a guessed target.
3. For instructions such as recoloring, consult instruction_edit support. If false, display the limitation/error. **Do not silently rewrite the instruction into a caption or fall back to img2img/txt2img.**
4. Only explicit user intent to make a whole-image variation/redraw selects operation=img2img/model=kobold-moss-img2img. Send a full caption, not a claim that local changes will be exact.
5. Surface400/422 errors. Do not interpret HTTP200/processing_success as semantic success; do not cache an error as a generated image.
6. Prompt-rewrite caching must include operation, target/reference roles and hashes, selected model/profile and strength. Generation prompts and edit instructions must not share a cache key.

Regression validation: unsupported recoloring/default edit, references, multiple targets, masks and wrong model produced422 without increasing the image-processing counter. JSON, multipart and A1111 real redraws at320×256/strength0.25 took approximately7.8–9.6s and produced source-dependent images. The blue square remained blue: this was deliberately not reported as successful recoloring. These are functional small-image tests, not full-resolution quality/timing measurements.
