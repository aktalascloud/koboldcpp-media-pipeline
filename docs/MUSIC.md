# YuE2 music / OWUI

[Detailed Russian filter specification](MUSIC.ru.md) · [Saved Russian MP3](../examples/yue2-russian-32s.mp3) · [Exact measurements](../benchmarks/music.json)

YuE2 Q8_0 + F16 VAE replaces ACE-Step. The client uses its existing helper LLM (tested NeoHorse) once to produce JSON `lyrics` and `style`; no Gemma or fixed remote server is required. Send those strings to `POST /api/extra/music/generate` with `cot:"off"`, `num_inference_steps:8`, `guidance_scale:1.01`, `duration:30`, `seed`, `use_mp3:true`, `stereo:true`. The response is binary MP3. No automatic `/prepare` round trip. Photo unloads for music and returns afterward.

The proxy converts duration to an approximate semantic token cap (25/s); exact duration is not guaranteed. Direct Native uses semantic_max_tokens. ACE-Step-only fields return422, empty Native audio returns502. `GET /v1/music/capabilities` documents the active family. Do not mix image CFG defaults into music or supply conflicting cfg_scale/guidance_scale.

32s diagnostic WAV:40.13s isolated generation; MP3 public request with NeoHorse lyrics:57.01s including model handoff, resident photo restored by61.07s. Peak sampled dedicated VRAM4419.60MiB/shared844.96MiB; no OOM in this short test. A separate16s direct MP3 took25.34s (26.84s with CPU helper loaded); identical MP3 bytes. CPU helperQwen4B:5.43s; remoteNeoHorse:5.89s, single requests, not an isolated hardware comparison. EXE6c03b583,28October2026. Long songs are not validated. The user accepted Russian vocals on the saved short trial; official model language tags are Chinese/English.

Main weights are downloaded from [audio-cpp/Yue2-3B-GGUF](https://huggingface.co/audio-cpp/Yue2-3B-GGUF), pinned in models.json. They are not mirrored. CC-BY-NC-4.0 applies; [upstream YuE2](https://huggingface.co/m-a-p/YuE2-3B). Photo settings are unchanged.
