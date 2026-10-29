# Component licenses and attribution

Original wrapper code: AGPL-3.0. Every runtime/checkpoint has independent terms. Neither this repository license nor a mirror changes the model author's grant.

| Component | Source / terms | Current distribution |
|---|---|---|
| Optimized KoboldCpp |[fork](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa), [original](https://github.com/LostRuins/koboldcpp); AGPL/MIT notices|Pinned core release, exact corresponding source at its tag.|
| Artius custom text/VAE (previous image is inactive) |[author](https://civitai.com/models/3010191?modelVersionId=3416029), exact hashes in models.json|No main weights or converted GGUF distributed. Author metadata: derivatives=false, differentLicense=false; commercial flags Image/RentCivit. Check original terms/access for your use. Local format-conversion code does not grant additional rights.|
| Official MOSS base/SFT |[OpenMOSS](https://huggingface.co/OpenMOSS-Team/MOSS-Image-Base), Apache-2.0|Not silently substituted for Artius; base license does not erase finetune restrictions.|
| Qwen3.5 tokenizer |[Qwen](https://huggingface.co/Qwen/Qwen3.5-9B), Apache-2.0|Pinned original download.|
| GGUF writer/quantizer subset |[exact native-source tree](https://github.com/LostRuins/koboldcpp/tree/329f6a5b31e9a1036ff862f8a0c694bd2fc6c98c/gguf-py), MIT|Unchanged source subset, MIT notice retained; minimal package initializer.|
| YuNet |[OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet), MIT|Verified checkpoint in original pinned asset; notice retained.|
| SFace |[OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface), Apache-2.0|Verified checkpoint; notice retained.|
| GPEN512 ONNX |[GPEN](https://github.com/yangxy/GPEN), [FaceFusion terms](https://docs.facefusion.io/introduction/licenses)|Non-Commercial according to distributor; complete original redistribution grant not located. New code release does not mirror weights; users obtain/supply the original ONNX. No MIT/unrestricted-use claim.|
| Gater Restore1Р В Р’В Р Р†Р вЂљРЎС™Р В Р вЂ Р В РІР‚С™Р Р†Р вЂљРЎСљ |[Philip Hofmann / Phhofm](https://github.com/Phhofm/models/releases/tag/1xgaterv3_r_restore), CC-BY-4.0|Original FP32 ONNX in pinned base asset, attribution retained.|
| Historical Helaman /4xNomos8k_atd_jpg, not installed |[Philip Hofmann / Phhofm](https://github.com/Phhofm/models/releases/tag/4xNomos8k_atd_jpg), CC-BY-4.0|Fixed-shape FP32 ONNX derivative; attribution/change record retained. Helaman uploader loonalone; no author endorsement. Reflected tiling is approximate, not guaranteed whole-frame equivalence.|
| ATD architecture / Spandrel |Apache-2.0 / MIT|Original texts retained.|
| Python, NumPy, Pillow, Torch CPU, ORT DirectML/Extensions, OpenVINO, OpenCV |Bundled licenses/third-party notices|Pinned runtime-only subset; no training state, logs or credentials.|
| AceStep music |[KoboldCpp music](https://huggingface.co/koboldcpp/music), per-model terms|Primary-host downloads; no music GGUF in Git/releases.|

CC-BY source hashes, changes and attributions are in `licenses/Gater-ATTRIBUTION.json` and `licenses/Helaman-ATTRIBUTION.json`. Generated gallery examples are this installation's saved outputs, not uploaded user/reference photos or browser screenshots. PNG metadata was stripped without changing RGB pixels; one explicitly labeled overview thumbnail is resized. The gallery manifest records every crop/source/hash.

Historic release assets remain available for pinned older versions. Their presence is not a new unrestricted-license claim. Current Setup does not install obsolete Z-Image LoRAs and does not download the historic GPEN mirror.
## Current additions
- Refined Realism original/converted main weights are **not distributed**. Author URL/license metadata were not verified; users supply the exact original with appropriate rights. Base MOSS Apache terms alone do not establish finetune rights.
- ClearRealityV1 Normal by Kim2091: [original card](https://huggingface.co/Kim2091/ClearRealityV1), Apache-2.0. Unmodified FP32 ONNX downloaded from a pinned original revision; full license and notice in licenses/ClearReality-*.txt.
- Source/runtime asset reuse preserves original notices. Current extraction excludes unused Helaman weights and its Torch dependencies. Historic release assets are unchanged for old pinned installers.

## Current Dirty adapters
Dirty MOSS [author version3423156](https://civitai.com/models/3015644?modelVersionId=3423156), turbo [author version3420002](https://civitai.com/models/3006599?modelVersionId=3420002), [Afterlight3424873](https://civitai.com/models/3016917?modelVersionId=3424873), [Textslider3414043](https://civitai.com/models/3008688?modelVersionId=3414043): links and fingerprints only; no weight redistribution or inferred permissive license. The exact resized turbo is user-supplied. Author access/usage terms remain the installer user's responsibility; no author card or private training metadata is embedded. Existing AGPL/MIT/runtime/GPEN notices are retained.

## Current Ray assets
Ray Artshoot [version3426693](https://civitai.com/models/3018302?modelVersionId=3426693) and [Afterlight3424873](https://civitai.com/models/3016917?modelVersionId=3424873): original author terms, links/hashes only, no weights mirrored or inferred permissive license. Optional Dirty/turbo follow original terms; exact resized turbo is user-imported. Existing AGPL/MIT/Apache/CC-BY/GPEN Non-Commercial notices and aria2/GMP source hashes retained.


YuE2 music supersedes previous ACE-Step references: Q8_0 main + F16 VAE, no Gemma, client-side helper, MP3. See [music contract](MUSIC.md). Original pinned weights download only; CC-BY-NC-4.0 and upstream attribution apply. No song-generation claims beyond the saved short trials.

## Pro, interpolation and current quality adapter
- RealismEnhancerV1 [author version3433342](https://civitai.com/models/3023438?modelVersionId=3433342): original author terms; links/hashes only, no weight mirror or inferred permissive grant.
- Pro decoder: [LightVAE original model card](https://huggingface.co/lightx2v/LightVAE), Apache-2.0 declaration. Setup obtains exact original checkpoint and pinned ModelTC source directly; upstream ModelTC Python is not mirrored because a separate repository license was not located. Our export wrappers and source fingerprints are included; model terms remain applicable.
- Optional RIFE ncnn [original release](https://github.com/nihui/rife-ncnn-vulkan): original downloads and their LICENSE. No Microsoft vcomp DLL redistributed. Optional private local runtime discovery does not establish redistribution rights.
- FFmpeg/codec binaries retain their original distributor licenses and corresponding-source links in existing notices. The code kit does not include new codec binaries or model weights.
