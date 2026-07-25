# Sample audio provenance

`tone_a.wav`, `tone_b.wav`, `tone_c.wav` are synthetic sine-wave tones
generated locally by `generate_samples.py` using Python's stdlib `wave`
module. They are **not** recordings of the real songs referenced in
`data/library.json` — they exist purely as small, license-free, real
playable audio bytes so the app's `st.audio()` player and format-support
guard have something genuine to work with.

License: CC0 / public domain (self-generated synthetic tones, no third-party
rights involved). This project runs fully local/offline (see
`docs/adr/0001-no-llm-local-only-agent.md`), so no audio was fetched from
the network — regenerate with:

```
python data/samples/generate_samples.py
```
