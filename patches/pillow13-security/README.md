# Pillow13 security dependency update

Apply change.patch to the media source repository at v2026.11.07-r2. Setup obtains the original Pillow13.0.0 CPython3.12 Windows wheel and the standalone pip26.1.1 wheel with exact SHA256 pins. Pip performs the package replacement after verifying the existing Pillow12.3.0 RECORD or the exact previously accepted portable binary hashes; modified files and unexpected versions are preserved. Run Setup with the service closed; local deployment uses its owned idle lock. Runtime requirements/versions are updated without model or profile changes. No wheel or private runtime is mirrored.

Nine saved-image/processing controls retained exact pixels. [Security evidence](../../results/security-2026-11-07.json) and [official fixes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html). Pillow uses HPND and codec notices; pip is MIT.

The code kit carries current13.0.0 dependency metadata. Setup skips older base-image metadata and preserves an already-updated Pillow13 package while unpacking the reused runtime asset. Fresh installs update the verified old package before model loading or master creation.
