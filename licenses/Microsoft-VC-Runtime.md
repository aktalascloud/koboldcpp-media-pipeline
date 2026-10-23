# Microsoft runtime components

The portable CPython/Torch runtime uses unmodified app-local Microsoft Visual C++ runtime DLLs. These remain Microsoft components under their vendor terms; the project's AGPL and model licenses do not relicense them. They are dependencies, not graphics drivers. No system copy is modified.

Vendor redistribution documentation: https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170 . Redistribution list: https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution . Official current redistributable: https://aka.ms/vs/17/release/vc_redist.x64.exe . Follow Microsoft's terms for your deployment; no additional grant is asserted by this notice.

App-local closure includes vcruntime140, vcruntime140_1, msvcp140, msvcp140_1, msvcp140_2, concrt140, VCRUNTIME140_THREADS and MSVCP140_ATOMIC_WAIT. Python's own license is retained under runtime/python/LICENSE.txt; Torch and other packages retain their complete bundled licenses/third-party notices.
