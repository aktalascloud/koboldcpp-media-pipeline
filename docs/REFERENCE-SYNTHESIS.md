# Reference synthesis with any vision provider

This workflow keeps the installed MOSS generator. It does not install another model, turn MOSS into a vision model, or provide native reference/identity conditioning.

1. OWUI sends2–4 explicitly identified photos plus the user request to its selected existing vision model.
2. In one call, that model describes each source and composes a declarative English caption for the new image (up to180 words).
3. `POST /v1/images/synthesize` validates roles/descriptions/hashes and sends **only that caption** to MOSS. Normal/High, faces/Gater and optional4× follow the existing pipeline.

The analyzer/provider is not hardcoded. The server has no vision-provider URL/key and makes no external analysis call. Use `GET /v1/images/synthesis-schema` for the universal analysis system prompt, example schema and limits. `GET /v1/images/capabilities` advertises this as a distinct operation.

## Request

```json
{
  "operation": "reference_synthesis",
  "model": "kobold-moss",
  "sources": [
    {"id":"image1","role":"base","image_sha256":"64_HEX_DIGITS","description":"Visible composition, pose, clothes and lighting.","use_for":["composition","pose","background"]},
    {"id":"image2","role":"reference","image_sha256":"64_HEX_DIGITS","description":"Visible appearance requested from this source.","use_for":["appearance"]}
  ],
  "user_request": "Use the scene from image1 and appearance details from image2.",
  "generation_prompt": "The complete final descriptive caption composed by your chosen analysis model.",
  "enable_hr": true
}
```

Exactly one source is base;1–3 are references. IDs must be unique; hashes bind analyses to original uploaded bytes. The server cannot verify those hashes or descriptions without the raw images, and reports that limitation. Raw photo bytes/URLs, missing analyses/final caption and unsupported exact-identity fields are rejected instead of ignored. Current image-profile overrides are accepted only when they match the server's selected settings.

The response includes `conditioning:text_descriptions_only`, `native_reference_conditioning:false`, `exact_identity_guaranteed:false`, `semantic_success_evaluated:false`. A face can resemble the described traits; exact transfer of a particular person's face is not guaranteed. This is a NEW generated image, not an unchanged photograph with a precise local replacement. Ordinary instruction-edit/reference-conditioned edits remain unsupported on `/v1/images/edits`.

## OWUI integration

`tools/ReferenceSynthesisClient.py` uses only Python's standard library. Import `build_synthesis_payload` into the existing filter or use its logic:

```python
schema = await get_json(kobold_url + "/v1/images/synthesis-schema")
payload = await build_synthesis_payload(
    sources, user_request, vision_call,
    analysis_prompt=schema["vision_system_prompt"],
    analysis_model=selected_model_id,
    generation_options={"enable_hr": True}
)
result = await post_json(kobold_url + "/v1/images/synthesize", payload)
```

Each source contains original `image_bytes`, id, role and use_for. `vision_call(messages)` is a sync/async callback to OWUI's currently selected vision provider; it returns the requested JSON object/string, not an OpenAI envelope. It is called once with all pictures. No provider/model name or credentials are fixed in this helper. Roles/hashes/request are preserved from caller inputs, rather than trusted to model guesses.

Do not silently fall back from an unsupported precise-edit request. Offer/reference this synthesis workflow explicitly and label the result as generated from descriptions. Cache analyses by source bytes+roles+analyzer/template version; cache final captions additionally by user request, image-profile options and source uses. A later correction may reuse unchanged visual descriptions and ask the selected LLM for a new caption.

Validation: callback/role/hash contracts and rejection cases were checked offline; one actual MOSS request from truthful manually prepared simple-source descriptions produced a red square at320×480 in23.92s. This verifies the generation handoff, not external OWUI vision quality or exact face identity. No new model weights were installed.
