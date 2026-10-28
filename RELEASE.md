Wan5B video API · user-selected Super-Tiny default · optional 720p

- Adds `/v1/videos/generations` and `/v1/videos/upscale`: one start PNG or text, MP4/Range output, exclusive GPU handoff and automatic resident-photo recovery. [API instructions](docs/VIDEO.md).
- Actual public 17-frame Super-Tiny cycle: **98.01s** for **0.71s** of video, including ClearReality720p and guarded GPEN/SFace. Photo returned by **118.27s**. [Scoped proof](benchmarks/video.json).
- User chose speed over the visible loss of face/eye detail: the full Wan encoder now feeds the Super-Tiny decoder by default. The 49-frame Native comparison was 140.06s versus 831.11s for full VAE. These compare complete VAE/tiling configurations. Continuous 30-second quality/speed is unvalidated.
- Ray photo and YuE2 music settings remain unchanged; their dated results were not remeasured. [Optimized Native build](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa).
- Minimal code-only kit; weights and FFmpeg download from pinned original sources. MIT/AGPL/GPL/model notices retained. No model mirrors, keys, caches or logs.
