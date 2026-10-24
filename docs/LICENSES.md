# Component licenses and attribution

Original wrapper code: AGPL-3.0. Every runtime/checkpoint has independent terms. Neither this repository license nor a mirror changes the model author's grant.

| Component | Source / terms | Current distribution |
|---|---|---|
| Optimized KoboldCpp |[fork](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa), [original](https://github.com/LostRuins/koboldcpp); AGPL/MIT notices|Pinned core release, exact corresponding source at its tag.|
| Artius MOSS image/custom text/VAE |[author](https://civitai.com/models/3010191?modelVersionId=3416029), exact hashes in models.json|No main weights or converted GGUF distributed. Author metadata: derivatives=false, differentLicense=false; commercial flags Image/RentCivit. Check original terms/access for your use. Local format-conversion code does not grant additional rights.|
| Official MOSS base/SFT |[OpenMOSS](https://huggingface.co/OpenMOSS-Team/MOSS-Image-Base), Apache-2.0|Not silently substituted for Artius; base license does not erase finetune restrictions.|
| Qwen3.5 tokenizer |[Qwen](https://huggingface.co/Qwen/Qwen3.5-9B), Apache-2.0|Pinned original download.|
| GGUF writer/quantizer subset |[exact native-source tree](https://github.com/LostRuins/koboldcpp/tree/329f6a5b31e9a1036ff862f8a0c694bd2fc6c98c/gguf-py), MIT|Unchanged source subset, MIT notice retained; minimal package initializer.|
| YuNet |[OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet), MIT|Verified checkpoint in original pinned asset; notice retained.|
| SFace |[OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface), Apache-2.0|Verified checkpoint; notice retained.|
| GPEN512 ONNX |[GPEN](https://github.com/yangxy/GPEN), [FaceFusion terms](https://docs.facefusion.io/introduction/licenses)|Non-Commercial according to distributor; complete original redistribution grant not located. New code release does not mirror weights; users obtain/supply the original ONNX. No MIT/unrestricted-use claim.|
| Gater Restore1× |[Philip Hofmann / Phhofm](https://github.com/Phhofm/models/releases/tag/1xgaterv3_r_restore), CC-BY-4.0|Original FP32 ONNX in pinned base asset, attribution retained.|
| Helaman /4xNomos8k_atd_jpg |[Philip Hofmann / Phhofm](https://github.com/Phhofm/models/releases/tag/4xNomos8k_atd_jpg), CC-BY-4.0|Fixed-shape FP32 ONNX derivative; attribution/change record retained. Helaman uploader loonalone; no author endorsement. Reflected tiling is approximate, not guaranteed whole-frame equivalence.|
| ATD architecture / Spandrel |Apache-2.0 / MIT|Original texts retained.|
| Python, NumPy, Pillow, Torch CPU, ORT DirectML/Extensions, OpenVINO, OpenCV |Bundled licenses/third-party notices|Pinned runtime-only subset; no training state, logs or credentials.|
| AceStep music |[KoboldCpp music](https://huggingface.co/koboldcpp/music), per-model terms|Primary-host downloads; no music GGUF in Git/releases.|

CC-BY source hashes, changes and attributions are in `licenses/Gater-ATTRIBUTION.json` and `licenses/Helaman-ATTRIBUTION.json`. Generated gallery examples are this installation's saved outputs, not uploaded user/reference photos or browser screenshots. PNG metadata was stripped without changing RGB pixels; one explicitly labeled overview thumbnail is resized. The gallery manifest records every crop/source/hash.

Historic release assets remain available for pinned older versions. Their presence is not a new unrestricted-license claim. Current Setup does not install obsolete Z-Image LoRAs and does not download the historic GPEN mirror.