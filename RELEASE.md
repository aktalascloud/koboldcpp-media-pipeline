## English

Haswell AVX2 and Polaris Vulkan · 2026-11-11. Reuses YuE2 guidance logits, packs text candidates and removes a PNG copy. The loader rejects zero recurrent ranks.

YuE2 43.90 → 43.91 s. ABDM Normal + separate 4× 153.52 → 153.92 s by phase medians. Text, PCM and RGB matched.

## Русский

Haswell AVX2 и Polaris Vulkan · 2026-11-11. Повторное использование логитов YuE2, упаковка кандидатов текста и устранение копии PNG. Загрузчик отклоняет нулевые ранги рекуррентных моделей.

YuE2 43.90 → 43.91 с. Сумма медиан ABDM Normal и отдельного 4× 153.52 → 153.92 с. Текст, PCM и RGB совпали.

[Timings / Замеры](results/performance-2026-11-11-multimodal.json) · [Operations / Операции](results/operations-2026-11-11-multimodal.json) · [PR diffs / Диффы](results/pr-review-2026-11-11-multimodal.json).

[Native patches / Патчи](https://github.com/aktalascloud/koboldcpp-avx2-vulkan-numa/tree/concedo_experimental/performance/patches/series).
