# Encode LightVAE-Pro AVI and MP4 from one RGB stream

Pass the same RGB frames to FFV1 and libx264 in one bundled FFmpeg invocation. This removes a second process startup and the lossless AVI decoding stage. Both artifacts retain their formats. The worker reports the encoding duration independently of ONNX decode.

On a 49-frame 832×480 clip, the median of three runs fell from 0.624 s to 0.366 s. Decoded AVI frames and MP4 bytes matched across all runs. The speed figure applies to encoding. [RX 580 and Haswell measurements](../../benchmarks/2026-11-16-calibration-rx580.json)
