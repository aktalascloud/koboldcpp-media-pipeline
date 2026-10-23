SD-Qwen counter data for the existing KoboldCpp1.123.1 Native tokenizer.
The merge resource is extracted from the original installed EXE; no replacement Qwen/model/tokenizer was downloaded.
native_counter.py is a bit-exact copy of the prototype validated against828 saved Native BPE pieces and4 new Russian/weighted/Unicode/UTF8 golden requests.
The regex wheel and license are local in deps/. Non-runtime regex/tests are omitted; upstream dependency metadata is retained unchanged.
ImageBudget.py must run after normal image profile/trigger handling and final geometry preparation. It never modifies the prompt; ordinary Native3000-UTF8-byte handling is only reproduced locally for counting.
Runtime LoRA tag handling remains explicitly unsupported rather than silently rewriting user text. Missing/tampered assets are an image error, not permission to fall back toCPU.
Source: https://github.com/LostRuins/koboldcpp/tree/9be8c136ae7e17eb50d9b7a6f3dff5038fcc3186/otherarch/sdcpp/src/tokenizers
