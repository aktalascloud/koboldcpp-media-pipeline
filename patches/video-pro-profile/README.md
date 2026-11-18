# Reduce LightVAE-Pro decode overhead

The pinned FP32 graphs profile one run per executed graph and keep the check for heavy CPU operations. Unknown graphs retain full profiling. Decoder accumulation reuses its FP32 buffer and keeps the original rounding order.

On RX 580 2048SP and Windows, the worker median for saved 17-frame Wan latents fell from 33.119 to 31.522 s on 2026-11-18. Three runs per arm produced identical RGB, AVI, MP4 and last-frame PNG hashes. Native `d9b2e6b5` supplied the latents. Fixed DirectML dimensions failed initialization on this driver during a separate trial. [Runs and hashes](../../docs/evidence/video-post-ab-20261118.json).
