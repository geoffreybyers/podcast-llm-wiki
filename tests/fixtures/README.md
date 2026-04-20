# tests/fixtures/

Test data used by unit and integration tests.

## short-clip.wav (NOT committed)

The integration smoke test (`tests/integration/test_smoke.py`) needs a
~30-second mono 16 kHz WAV file. To set up:

```bash
# Option A: generate a synthetic clip from text-to-speech (any tool)
ffmpeg -i <some-source.mp3> -ar 16000 -ac 1 -t 30 short-clip.wav

# Option B: use any short public-domain audio you have locally
ffmpeg -i <pd-audio.wav> -ar 16000 -ac 1 -t 30 short-clip.wav
```

The file is gitignored; do not commit copyrighted audio.
