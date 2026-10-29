Unified KoboldCpp media API · Pro video and YuE2 soundtrack

- Adds true Wan latent-only export followed by Pro FP32 DirectML. Tiny/Super-Tiny are removed from the active media chain. Native unloads before GPU postprocessing; image residency returns automatically.
- One `/v1/videos/generations` call produces MP4 with optional ClearReality720p, guarded faces, optional RIFE and a separate YuE2 musical track. No joint audio-video/Foley/lip-sync claim. [API](docs/VIDEO.md).
- Local17-frame video API probes with a user adapter completed in190.76s and258.05s;0.71s of footage, not17seconds. Queue/load scope and every matrix arm are preserved. Public kit does not enable the private adapter. [Measurements](benchmarks/video.json).
- Selected photo recipe: RayQ8 + Afterlight0.25 + RealismEnhancer1.0 / Euler-simple8. Real Normal163.85s, separate ordinary4×6.04s. MoodyV3.3/Turbo and quality-adapter alternatives are documented. [All arms](benchmarks/image-current.json).
- Original model downloads and one-time Pro CPU conversion; no large model mirrors, private Microsoft runtime, keys, caches or logs. Source/license notices and pinned base assets retained. [Optimized Native build](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa).
