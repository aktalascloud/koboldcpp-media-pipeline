# Components, licenses and downloads

This repository's original wrapper code is AGPL-3.0. Models and runtime dependencies have independent licenses. License texts and attribution are retained in release assets; no license of a mirror is taken to override an original model license.

| Component | Source / terms | Distribution |
|---|---|---|
| Optimized Kobold |[fork](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa),AGPL-3.0 + upstream notices|Exact accepted EXE in core releases; corresponding source at tag.|
| Moody Pro Mix |[author Civitai page](https://civitai.red/models/620406?modelVersionId=3161628); exact collectorsEdition file|Not redistributed.|
| Qwen encoder |[exact HF quant](https://huggingface.co/mradermacher/Qwen3-4B-Instruct-2507-heretic-uncens-i1-GGUF), heretic-uncens-i1 IQ4_XS|Not redistributed; check manifest/source link.|
| Z-Image/FLUX-compatible VAE |Original model author's download; retain its terms|Download/supply locally.|
| PhysioShade |[jarod2212](https://huggingface.co/jarod2212/PhysioShade_ZIT),Apache-2.0|Apache-2.0 weight asset; trigger physioshade.|
| FlowDPO |[F16](https://huggingface.co/F16/z-image-turbo-flow-dpo),Apache-2.0|Apache-2.0 weight asset.|
| MaskedDPO |[F16](https://huggingface.co/F16/z-image-turbo-masked-dpo),Apache-2.0 confirmed by public model API, original gated access|Compatible Full derivative in the Apache-2.0 weight asset, with conversion notice/source hash; no HF token or contact data.|
| YuNet |[OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet),MIT|License retained.|
| SFace |[OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface),Apache-2.0|License retained.|
| GPEN512 ONNX |[GPEN author](https://github.com/yangxy/GPEN),[FaceFusion converter labels Non-Commercial](https://docs.facefusion.io/introduction/licenses)|Separate optional non-commercial asset, explicitly requested by the maintainer. Not relicensed AGPL/MIT. No unrestricted-commercial-use or settled original-license claim.|
| Gater Restore1x |[Phhofm release](https://github.com/Phhofm/models/releases/tag/1xgaterv3_r_restore),CC-BY-4.0|Author Philip Hofmann; original FP32 ONNX.|
| Helaman /4xNomos8k_atd_jpg |[Phhofm original](https://github.com/Phhofm/models/releases/tag/4xNomos8k_atd_jpg),CC-BY-4.0|Author Philip Hofmann; Helaman uploader loonalone. FP32 fixed-shape ONNX derivative, original unstable sort, reflected tiling; no whole-frame equivalence claim.|
| ATD architecture /Spandrel converter |Apache-2.0 /MIT|Texts retained; converter is not required at runtime.|
| Python /NumPy /Pillow /Torch CPU /ORT DirectML /ORT Extensions /OpenVINO /OpenCV |Their bundled original licenses and third-party notices|Runtime-only subset, no training cache/logs or installer credentials.|
| AceStep music weights |[KoboldCpp HF organization](https://huggingface.co/koboldcpp/music),follow exact per-model terms|Downloaded separately; no music GGUF in Git.|

CC-BY changes and source attributions are recorded in licenses/Helaman-ATTRIBUTION.json and Gater-ATTRIBUTION.json. No endorsement by model authors is claimed. Generated benchmark examples are outputs of this installation; no user's uploaded reference photos or browser screenshots are included.
