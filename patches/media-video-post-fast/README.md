# Cheaper video post-processing

Production skips five diagnostic PNGs. The API keeps its last-frame PNG. FFmpeg receives a byte view of the RGB array. Face motion compensation reuses its coordinate grid at the current frame size.

Windows Xeon E5-2696 v3 (10 cores visible), Native `d9b2e6b5`, 2026-11-17. CPU Lanczos and H.264 at 720×1248, 24 FPS.

| Fixture | Before | After | Result |
|---|---:|---:|---|
| 32 frames, no face processing | 1.055 s median | 0.598 s median | 3 runs per arm, decoded frames identical |
| 8 frames with OpenVINO face processing | 12.871 s | 11.583 s | 1 pair, all 8 faces processed, decoded frames identical |

The last-frame PNG matched in both checks. The table measures the post-processing stage from a saved clip.
