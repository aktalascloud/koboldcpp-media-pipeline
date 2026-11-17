# Faster temporary PNG extraction for RIFE

FFmpeg writes the temporary PNG frames at compression level 1. RIFE reads the same lossless pixels. The video encoder and frame interpolation are unchanged.

Three runs per arm on 32 frames, Xeon E5-2696 v3 and Windows. Median extraction fell from 0.548 s to 0.205 s. The decoded frame hashes matched. Temporary PNGs grew from 19.0 MB to 22.9 MB and are removed by the interpolation job.
