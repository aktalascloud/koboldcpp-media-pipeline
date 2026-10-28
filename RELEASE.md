YuE2 music · NeoHorse/OWUI · photo settings unchanged

- Replaces ACE-Step with YuE2 Q8 + F16 VAE; no Gemma. Existing client helper composes lyrics/style once. [OWUI rules](https://github.com/aktalascloud/koboldcpp-media-pipeline/blob/main/docs/MUSIC.ru.md).
- One32s MP3 request: **57.01s** including model handoff; resident photo restored by61.07s. Isolated32s diagnostic:40.13s; peak4419.60MiB dedicated VRAM, no OOM. User accepted Russian short-trial vocals; long songs untested.28Oct2026,EXE6c03b583. [Proof](https://github.com/aktalascloud/koboldcpp-media-pipeline/blob/main/benchmarks/music.json) / [MP3](https://github.com/aktalascloud/koboldcpp-media-pipeline/blob/main/examples/yue2-russian-32s.mp3).
- Family-aware startup/model guards, duration-to-token mapping, old ACE fields422 and empty Native audio502. Ray photo profiles/face restoration/SR unchanged; no native rebuild.
- Code-only kit, pinned original weight downloads; YuE2 CC-BY-NC-4.0. No model weights, secrets, caches or logs mirrored. Existing third-party attribution/licenses retained.
