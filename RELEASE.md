Media security and SDCPP update · 2026-11-07

- Core1.125 `0519dcbf`,official `9958bb2`,58 Native patches. SDCPP memory planning/reclamation and integer LoRA fixes retain existing model math/settings.
- Pillow12.3.0→13.0.0 from original hash-pinned wheels;9 saved-image/processing controls retain exact pixels. [Separate patch](patches/pillow13-security/README.md) · [Security scope](results/security-2026-11-07.json).
- One portable master,unchanged profiles. [Operation checks and first-miss costs](results/operations-2026-11-07-r4.json).
- Runtime/model base assets are reused; Setup applies the Pillow security update before loading models or building its local master. No main or non-commercial weights mirrored.

Manual Normal+4×: **187.107→158.073s**, **29.034s / 15.52% less time**,sum of independently measured phase medians. Same settings/seed,no High,exact RGB. [All repeats,cohort identities and scope](results/performance-2026-11-07-r3.json). No new LLM token benchmark.
