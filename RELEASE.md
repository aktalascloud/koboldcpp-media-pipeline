Startup reliability and standalone SFX

- Recover previous-boot incomplete intents only after ownership/slot checks. Retry Windows atomic JSON replacement on transient sharing denial; permanent errors stay visible. Duplicate logon launches now share one entry lock.
- Start.exe opens only the universal KoboldCpp.exe. Setup builds the master locally; native engine stays an internal component.
- New POST /v1/audio/sfx returns real WAV/MP3,0.25–60s, using SA3 CPU without switching the image model. [Contract](docs/SFX.ru.md). No new token/photo/video speed claim.
- Private addresses and the owner-local runtime bundle are not mirrored. [Portable OWUI spec](docs/OWUI-T2V-I2V-AUDIO-TZ.ru.md).
