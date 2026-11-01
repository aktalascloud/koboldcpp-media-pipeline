# Media API / OWUI
[Full Russian implementation specification](API.ru.md). Configure http://YOUR_KOBOLD_HOST:5001; port5003 shares the same queue. Native5005 is internal. Discover /openapi.json, /v1/media/capabilities, /v1/videos/capabilities and /v1/audio/capabilities. Models and numerical presets belong to GUI/.kcpps, not checkpoint names embedded in a filter.

| Operation | POST endpoint | Required/core fields |
|---|---|---|
| Image | /sdapi/v1/txt2img or /v1/images/generations | prompt; Normal is default |
| Whole-frame redraw | /v1/images/edits | operation:img2img, one target, prompt |
| Image4x | /sdapi/v1/extra-single-image | image(Base64), upscaling_resize:4 |
| Music MP3 | /api/extra/music/generate | style, lyrics, duration(approximate cap) |
| Video | /v1/videos/generations | prompt, frames, optional image(PNG Base64) |
| Stored-video audio | /v1/videos/soundtrack | video_id, audio(tracks/speakers) |
| Movie import | /v1/videos/import | binary video/mp4, CFR24/48/60, up to30s/2MP |
| Stored-video RIFE | /v1/videos/interpolate | video_id,fps:48 or60; input24FPS |
| Mouth / voiceover | /v1/videos/lipsync | video_id,mode,speech; explicit target_box for onscreen |
| SFX WAV/MP3 | /v1/audio/sfx | prompt(English), duration0.25..60, seed, response_format |
| Speech WAV | /v1/audio/speech | input, voice, language, response_format:wav |
| STT | /v1/audio/transcriptions | compatible multipart audio |

Image model/adapters/sampling are server-owned: RayQ8, Afterlight.25+RealismEnhancer1, Euler/simple8/eta0/CFG1/shift5, Cache-DiT.08. Normal736x1104 noautoSR; enable_hr:true requests proxyClear4x. High: kcpp_quality:quality,928x1392,default4x. High current adapter mix has no new timing. Faces/Gater run before SR, not again afterwards. GUI uses original Image Gen/Audio plus Video; Extra has language/startup; arbitrary.kcpps Save/Load.

Image edits are whole-frame img2img, not instruction editing. Unsupported masks/multiple-reference/instruction operations return422 without a fake successful image. /v1/images/synthesize accepts2–4 client vision TEXT analyses, not image conditioning or guaranteed identity.

Native video:480p, frames4n+1,5..121 at24FPS.73 frames are the tested conservative clip size;121 is a loader limit, not a900s completion guarantee. Output defaults to real RIFE48FPS; interpolate_fps:60 requests60. Keep server sampling/cache/LoRA/VAE settings. PNG limit16MiB; resolve returned relative URLs against the configured server. RIFE does not extend motion duration;60FPS rounding is less than one output frame.

Client project:15s default,30s maximum. Generate sequential73-frame clips with audio:false,interpolate_fps:24 and continue_from; remove shared boundary frames and trim to exact24FPS duration.15/30s require5/10 clips. Never loop or slow footage. Import the assembled MP4, then apply RIFE once. Exact montage may require one reencode. Seamless long identity/motion and full15s AI rendering have not been validated.

Analyze actual frames with the chosen OWUI vision model. /v1/media/audio-plan takes observed events/timestamps in prompt,duration_seconds,speakers; its configured helper is text-only. JSON Schema with at most one repair. Tracks:0..8, kind music/sfx/speech,start,end,volume; quiet scenes may return tracks:[]. Add only requested/observed effects, not constant wind/hiss. Standalone SFX returns binary WAV/MP3. Use one continuous music track per project; ordinary timed mixing is not joint audiovisual generation.

Voices: ru/shimmer=Masha, ru/sage=Sveta, ru/echo=Dima; en/shimmer=Heart, en/Ryan=Michael. Always set language; aliases are not extra voices. Retain a stable role/language/profile/voice mapping; speaker.voice supports explicit configured IDs. Do not infer gender from images. Music duration is approximate; speech that does not fit is rejected, not silently trimmed or accelerated.

Onscreen example: {"video_id":"32hex","mode":"onscreen","target_box":[0.4,0.1,0.15,0.2],"speech":{"text":"Maybe, baby, five.","voice":"shimmer","voice_profile":"female","speaker_id":"actor","language":"en","start":2}}. The normalized target rectangle is at speech start. Missing/ambiguous targets fail. Voiceover changes sound only; onscreen drives the mouth using actual audio. Optional Wav2Lip weights are non-commercial original-provider downloads. CPU short-speech processing preserves photo VRAM. No perfect identity/articulation guarantee.

For final mixing reuse onscreen speech_video_id, original start and fit:natural; do not rerun TTS. Actual length: metadata.mouth.speech_seconds. Exact WAV: metadata.speech_audio_url or /api/extra/video/media/{id}/speech.wav. Include every speech_segments entry after multiple speakers. Mixing copies video without another Wan/Pro/RIFE/lip-sync pass. Preserve referenced parent IDs/stems.

Generations accept Idempotency-Key: persist the exact payload. Same key/body reuses job/result; conflict409.202 means GET /v1/videos/jobs/{request_id}. After disconnect retry only the identical keyed request to recover its ID. Restarted unresolved jobs are unknown, not auto-retried. POST /v1/videos/jobs/{request_id}/cancel cancels queued work only. Other POSTs do not automatically share this contract.422 invalid/unsupported;503 backend/resource/monitor;504 budget, retained in the receipt after socket closure.900s is one clip budget, not the project.

Reuse the existing OWUI filter and configurable vision/helper selections. One Python file, existing FFmpeg/http client/storage. Client-side dedup and hash-based caches; no blind retry of expensive POST on lost response. Preserve ready video on audio failure. No shell commands/URLs supplied by LLM plans, private addresses in Git, or process-control/model-switch calls from the filter. Return files through authenticated OWUI storage. Timed audio is separate generators and mixing, not joint AV inference. Latest scopes/limits: ../results/measurements.json.
