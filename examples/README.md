# Existing benchmark images

The selected quality gallery is on the [main README](../README.md#selected-results), with [per-scene provenance](historical-scenes.json). The images below are historical performance controls, including known artifacts; they are not all selected quality examples.

No new generation was performed for publication. These images come from the same synthetic adult fashion/hotel/night/clock test, seed424242. PNGs were re-encoded only to remove metadata; RGB pixels were preserved. The subject is a generated adult, not a user's uploaded reference photo.

| Stock576×864 |New build576×864, same processing |
|---|---|
|![Stock](stock-photo.png)|![New](candidate-photo.png)|
|![Stock face](stock-face.png)|![New face](candidate-face.png)|
|![Stock eyes](stock-eyes.png)|![New eyes](candidate-eyes.png)|
|![Stock fabric](stock-fabric.png)|![New fabric](candidate-fabric.png)|
|![Stock legs](stock-legs.png)|![New legs](candidate-legs.png)|

The compiler comparison keeps the model/LoRA/sampler/refinement unchanged. Stock and new can differ in a few pixels; outputs of the two optimized builds were identical. Do not use this to claim perfect anatomy: the clock still has a baseline extra-hand defect.

Current larger Normal592×896, all3LoRA+faces+Gater,noSR,140.09s warm:

![Current Normal](normal-592x896-final.png)

Separately measured Helaman input608×912 and full4x2432×3648. Exclusive SR194.90s versus516.15s co-resident; final RGB byte-identical. This different input is deliberately labeled and is not a matched size comparison with592×896.

|Before SR608×912|After native4x2432×3648|
|---|---|
|![SR input](normal-608x912-final.png)|![Helaman4x](resident-normal-4x.png)|
