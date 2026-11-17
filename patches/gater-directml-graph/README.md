# Extended DirectML graph optimization for GaterV3

GaterV3 remains FP32 with request-local DirectML memory. ONNX Runtime uses Extended graph optimization.

On RX 580 2048SP / Windows, 4 warm runs per setting took 6.211 s before and 5.958 s after, including session creation. The RGB SHA-256 matched in every run. A second fixture also retained its RGB hash.
