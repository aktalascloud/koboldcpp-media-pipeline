# Video and soundtrack API

Wan2.2 TI2V5B Turbo Q4 uses the native Kobold backend. The full Wan encoder exports real48-channel posterior latents; the bounded Pro FP32 DirectML decoder produces RGB. Tiny/Super-Tiny are not used.480p generation, optional ClearReality720p and guardedYuNet/GPEN20%/SFace0.97 follow. A separateYuE2 music track can be muxed into the sameMP4 request. This is not joint audio-video generation,video-conditionedFoley orlip-sync.

`POST /v1/videos/generations`: `{"prompt":"A cinematic landscape with subtle cloud motion","frames":17,"resolution":"480p","orientation":"landscape","upscale_to":"720p","enhance_faces":true,"audio":{"enabled":true,"style":"Gentle cinematic instrumental,no vocals"}}`. Add`image` with PNG base64 forI2V. GET`/v1/videos/capabilities` and`/v1/media/capabilities` before sending optional features. The response contains anMP4 URL and measured stage metadata. Resolve relativeURLs against the configured server,not theOWUI host.

Use4n+1 native frames at24FPS; the demonstrated probe has17frames,about0.71seconds,not17seconds. The total request budget is450seconds. Longer clips and continuous30second motion remain unvalidated. OptionalRIFE48FPS adds interpolated frames without extending duration; it requires the optional originalRIFE runtime. The public kit does not enable the private local-test adapter. No video-model/adapter weights are mirrored.

Initial`Setup.ps1` downloads original weights and runs`tools/SetupPro.py` once onCPU using the same bundledPython. Source/weights/dependencies are pinned; after conversion,serving needs noPyTorch. Main MOSS/Qwen assets remain original downloads/user imports. Native unloads beforePro/SR andYuE2,then the image model is restored before a successful response.

[All local measurements and limits](../benchmarks/video.json) · [Full media API](MEDIA.ru.md) · [Russian video instructions](VIDEO.ru.md).
