# qarya-media

Production kit for Qarya's **Hospitality 101** explainer Reels: faceless, illustrated, fact-checked shorts that
Claude researches, writes, voices, animates and schedules twice a week.

- `RUNBOOK.md` — the weekly run, step by step
- `SCENES.md` — how to write an episode spec (scenes, timing, elements, layout)
- `topics/bank.json` — verified topics with what to say, what not to say, and sources
- `episodes/` — one folder per episode (spec, caption, sources)
- `kit/` — the engine: `make.py` (voice → preview → mix → video → deliver → check), `publish.py` (media branch)
- `brand/` — QIH logo files · `kit/fonts/` — Poppins, DM Serif Display, Playfair Display, Space Mono (SIL OFL)
- branch `media` — finished videos for Metricool to fetch (pruned regularly)

Third-party pieces fetched at setup: sherpa-onnx (Apache-2.0), Kokoro TTS v1.0 (Apache-2.0),
NVIDIA Parakeet TDT 0.6B v2 (CC-BY-4.0), Microsoft Fluent Emoji (MIT). Music and sound effects are synthesized by `kit/mix.py`.

Brand assets © Qarya Education Group. Not for reuse.
