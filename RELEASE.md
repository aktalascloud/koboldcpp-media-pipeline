Wan5B video API · full VAE quality default · optional 720p

- Adds `/v1/videos/generations` and `/v1/videos/upscale`: one start PNG or text, MP4/Range output, exclusive GPU handoff and automatic resident-photo recovery. [API instructions](docs/VIDEO.md).
- Actual public 17-frame cycle: **261.17s** for **0.71s** of video, including ClearReality720p and guarded GPEN/SFace. Photo returned by **281.95s**. Native EXE `6b05639f`, 28 October 2026. [Scoped proof](benchmarks/video.json).
- Full VAE preserved eyes better. A faster Super-Tiny configuration took 140.06s versus 831.11s for 49 frames, but lost detail; it is not the default. These compare complete VAE/tiling configurations. Continuous 30-second quality/speed is unvalidated.
- Ray photo and YuE2 music settings remain unchanged; their dated results were not remeasured. [Optimized Native build](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa).
- Minimal code-only kit; weights and FFmpeg download from pinned original sources. MIT/AGPL/GPL/model notices retained. No model mirrors, keys, caches or logs.
