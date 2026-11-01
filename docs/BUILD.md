# Install / rebuild
Windows64 Haswell/AVX2. Keep models, runtime and configuration in the same portable root; no absolute paths are required. On another LAN configure helper/TTS/STT and listen address in the GUI.

Initial installation: run Setup.ps1; forLAN add -ListenHost 0.0.0.0. Original large/gated model sources are supplied using -MossSourceDirectory; GPEN comes from its original Non-Commercial distributor using -GPENPath. Never mirror these files. Setup verifies hashes and preserves mismatched user files.

Setup installs pinned original runtime/core assets, converts original MOSS weights to Q8 if necessary, builds Pro once onCPU and creates KoboldCpp.exe locally. New SFX models download from original distributors; BuildSfx.py preserves an existing runtime or builds pinned SA3/ggml onCPU using original WinLibs and temporary cmake/ninja dependencies. No GPU SFX on RX580. This fresh-machine SFX build recipe is provided but has not been fully revalidated on a clean machine; the installed runtime is verified.

Run Start.exe (only opens KoboldCpp.exe). Extra enables Windows logon startup. Launch applies any selected.kcpps; Helper.kcpps is the internal snapshot. Source modules are in tools; models/processors/upscalers in MODELS; derived profiles in profiles; one runtime in runtime; all current proof/examples in results. Rebuild owner-local bundle: runtime/python/python.exe -I -B tools/BuildBundle.py. The complete private-MS-runtime bundle is not mirrored until redistribution review; public setup builds it locally. Native engine source/build: linked Core repository.

Do not change driver/BIOS/TDR/clock/voltage, precision, model hashes or inference defaults to fix packaging. GET-only startup checks by default; no automatic generation benchmarks.
