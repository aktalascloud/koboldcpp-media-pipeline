# Video with music, effects and speech

`POST /v1/videos/generations` accepts `audio.tracks` alongside the existing video fields. Each track has `kind`, `start`, `end` (seconds), and `volume` (0–1). The clip length is `frames / 24`; native frames must be 4n+1, between 5 and 121. The default request deadline is 450 seconds; an explicit `deadline_seconds` can raise it to 900. A longer clip is substantially slower, not a duration stretch of the 17-frame test.

```json
{
  "prompt": "A woman beside an open window, a gentle breeze moving the curtain, closed mouth, fixed camera",
  "frames": 121,
  "resolution": "480p",
  "orientation": "portrait",
  "deadline_seconds": 900,
  "upscale_to": "720p",
  "enhance_faces": true,
  "audio": {
    "enabled": true,
    "speakers": [{"id": "narrator", "voice_profile": "female", "language": "ru"}],
    "tracks": [
      {"kind": "music", "prompt": "Quiet acoustic instrumental, no vocals", "start": 0, "end": 5.04, "volume": 0.18},
      {"kind": "sfx", "prompt": "Gentle breeze and soft curtain rustling, no voices or music", "start": 0, "end": 5.04, "volume": 0.48},
      {"kind": "speech", "speaker_id": "narrator", "text": "Тёплый ветер. Мгновение тишины.", "start": 0.6, "end": 4.7, "volume": 0.9}
    ]
  }
}
```

Music uses YuE2; effects use SA3 Small SFX on the Haswell CPU; speech uses the configured external TTS. The server mixes up to eight tracks, limits peaks, and returns an MP4 with AAC audio plus a stereo MP3. The video stream is copied during audio muxing. Actual render/load/post times are returned in metadata.

For reviewed event timing, first generate with `audio:{"enabled":false}`. Let the client's chosen vision model inspect actual frames with timestamps, then pass its observations to the helper. `POST /v1/videos/soundtrack` accepts `{"video_id":"COMPLETED_VIDEO_ID","audio":{"enabled":true,"speakers":[...],"tracks":[...]}}`. It creates a new copy and replaces all prior audio; the original stays intact. Include music again if it should remain in the mix. Wan, Pro and SR are not rerun. This permits correcting footsteps after seeing actual motion instead of assuming the prompt was followed.

Manual30October2026, Native `0986410a`:73-frame I2V/3.04seconds at480p→Pro/Clear720/faces, music+SFX+Russian speech took552.57seconds in one HTTP call. A subsequent event-reviewed audio revision took57.96seconds; all73 decoded RGB frames remained identical. A121-frame T2V/5.04second probe passed in854.78seconds but was rejected visually because a curtain obscured the face. These differ in input/mode/cache and are not an isolated cache comparison. [Exact scope and stage times](../benchmarks/audio-video-20261030.json).

Speech requires an explicitly described `speaker_id` and `voice_profile` (`female` or `male`). Russian is the default: female→shimmer, male→echo. English: female→shimmer, male→Ryan. These are configured provider aliases, not universal voice IDs. The same speaker/language keeps its configured voice. GUI language does not change speech language. If speech does not fit, the request fails; explicit `fit:"stretch"` allows at most 2× tempo adjustment without changing pitch.

For automatic planning, set `audio.auto_plan:true`, supply `audio.prompt` and explicit `audio.speakers`. The selected helper produces a cached text-based timeline. Alternatively call `POST /v1/media/audio-plan`, inspect its tracks, and send them explicitly. The helper does not see the generated pixels. Accurate footsteps or impacts require reviewed event timestamps; music and continuous ambience can span the clip. This is **separate generation and timed mixing**, not joint AV inference, automatic visual Foley, or lip synchronization.

Configure the common helper/TTS/STT base URL and helper model in the native Audio tab. No provider is hardcoded. `GET /v1/audio/capabilities` reports availability; models, external addresses and credentials are not supplied in generation requests. Image Gen and Video retain the original file selectors; Extra contains RU/EN and logon startup. Save/Load uses any user-selected `.kcpps`.

## Optional SFX runtime

The owner-local portable bundle includes a tested CPU build of [sa3.cpp](https://github.com/betweentwomidnights/sa3.cpp) at `602af56e411bbff7a4140895cc906b76cfc5a74a` (MIT; ggml `b77ae790e628270af46a8af1eca38441c23f1252`). Its Vulkan build initialized this RX580 but crashed, so GPU SFX is not enabled. The minimal public code ZIP does **not** mirror this new runtime or the SFX weights. Install/build it separately in `runtime/sa3`; missing SFX is reported before video inference. Existing photo/music/video operation is independent of this optional component.

Original model downloads: [SA3 SFX GGUF](https://huggingface.co/thepatch/stable-audio-3-small-sfx-GGUF), [T5Gemma encoder](https://huggingface.co/thepatch/t5gemma-b-b-ul2-GGUF). Use Q8 DIT, Q8 SAME-S, F32 conditioner, F16 text encoder and vocabulary in `MODELS/audio/sfx`. Original Stable Audio community and Gemma terms apply; these weights are not MIT and are not redistributed here. Runtime dependencies retain their respective licenses.
