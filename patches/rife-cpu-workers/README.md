# Parallel RIFE loading and saving

RIFE v4.6 uses two loaders, one Vulkan processing worker and two savers. This overlaps CPU image read and write with the same Vulkan processing path.

On 2026-11-18 the 17-frame input returned 34 frames at 48 FPS in 2.704 s, down from 4.071 s. The same input returned 43 frames at 60 FPS in 3.743 s, down from 4.880 s. These are medians of two runs per arm on Windows with a Haswell Xeon and RX 580. MP4 hashes matched at each rate. [Runs and hashes](../../results/video-post-ab-20261118.json).
