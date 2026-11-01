# Media API
Base: http://YOUR_KOBOLD_HOST:5001 (alias5003). Private Native5005 is internal. GET /openapi.json and /v1/media/capabilities are authoritative. All JSON keys stay English; descriptions defaultRU, ?lang=en selectsEN where translated.

| Operation | POST endpoint | Required/core fields |
|---|---|---|
| Image | /sdapi/v1/txt2img or /v1/images/generations | prompt; Normal is default |
| Whole-frame redraw | /v1/images/edits | operation:img2img, one target, prompt |
| Image4x | /sdapi/v1/extra-single-image | image(Base64), upscaling_resize:4 |
| Music MP3 | /api/extra/music/generate | style, lyrics, duration(approximate cap) |
| Video | /v1/videos/generations | prompt, frames, optional image(PNG Base64) |
| Stored-video audio | /v1/videos/soundtrack | video_id, audio(tracks/speakers) |
| SFX WAV/MP3 | /v1/audio/sfx | prompt(English), duration0.25..60, seed, response_format |
| Speech WAV | /v1/audio/speech | input, voice, language, response_format:wav |
| STT | /v1/audio/transcriptions | compatible multipart audio |

Image model/adapters/sampling are server-owned: RayQ8, Afterlight.25+RealismEnhancer1, Euler/simple8/eta0/CFG1/shift5, Cache-DiT.08. Normal736x1104 noautoSR; enable_hr:true requests proxyClear4x. High: kcpp_quality:quality,928x1392,default4x. High current adapter mix has no new timing. Faces/Gater run before SR, not again afterwards. GUI uses original Image Gen/Audio plus Video; Extra has language/startup; arbitrary.kcpps Save/Load.

Image edits are whole-frame img2img, not instruction editing. Unsupported masks/multiple-reference/instruction operations return422 without a fake successful image. /v1/images/synthesize accepts2–4 client vision TEXT analyses, not image conditioning or guaranteed identity.

Video is Wan5B Turbo, full encoder+ProFP32, Euler/beta4, eta0/CFG1/shift5, lightCache.04,WG512,VAEthreshold576(actual320), native480p→Clear720/faces, optionalRIFE48FPS. One Native call: frames4n+1,5..121 at24FPS;121frames≈5.04s. PNG limit16MiB. Returned JSON has id,url,metadata. Resolve relative URLs against the Kobold base. Per-call deadline<=900s; default450. RIFE changes FPS, not duration.

OWUI20s default/60s maximum is an orchestration specification, not implemented native long-video support. Generate actual sequential short clips using continue_from; drop overlapping boundary frames, assemble and analyze the REAL finished movie. Never fake duration by looping/slowing video. Exact H.264 montage may need one final high-quality reencode; subsequent audio mux copies that assembled video stream. Long continuity/identity is not guaranteed. /v1/videos/soundtrack works only on stored native clipIDs, not a client-assembled long file.

After vision, a chosen helper can plan sound via /v1/media/audio-plan: prompt(actual observations/timestamps),duration_seconds,speakers. It is text-only, not vision. Tracks:1..8 per server request, kind music/sfx/speech,start,end(seconds),volume0..1; English prompt for music/SFX, text+speaker_id for speech. Individual SA3 impacts may need onset refinement; no lip-sync. New standaloneSFX returns BINARY audio/wav or audio/mpeg, not JSON/URL; headers X-SFX-Seconds and X-SFX-Generation-Seconds report duration/render time. LongSFX uses real short generations/crossfades. /v1/audio/sfx/capabilities reports availability.

Voices: ru/shimmer=Masha, ru/sage=Sveta, ru/echo=Dima; en/shimmer=Heart, en/Ryan=Michael. Always set language; aliases are not additional voices. Stable speaker_id/language→voice. Use explicit user roles or offscreen narrator, not gender inference from images. The server timeline selects female/male profiles, not per-trackvoice; for Sveta/multiple female voices, call TTS explicitly and mix on OWUI. For20–60s assembled movies mix music/SFX/TTS on OWUI after real-frame analysis. Music duration is approximate; speech must fit naturally, never silently cut. MP4 audioAAC; musicMP3; SFXwav/mp3.

Reuse the existing OWUI filter and configurable vision/helper selections. One Python file, existing FFmpeg/http client/storage. Client-side dedup and hash-based caches; no blind retry of expensive POST on lost response. Preserve ready video on audio failure. No shell commands/URLs supplied by LLM plans, private addresses in Git, or process-control/model-switch calls from the filter. Return files through authenticated OWUI storage. Timed audio is separate generators and mixing, not joint AV inference. Latest scopes/limits: ../results/measurements.json.
