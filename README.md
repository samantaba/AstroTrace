# AstroTrace

**SDR receiver & scanner with AI assist, Whisper STT, SigMF logging, audio playback, and plugin-friendly UI.**

![AstroTrace Logo](docs/logo.png) <!-- replace path if needed -->
![AstroTrace app](docs/app.png)
## Overview
AstroTrace is a cross-platform (macOS/Linux/Windows) SDR desktop app built with PyQt. It:
- Receives from RTL-SDR/SoapySDR (or synthetic IQ for demos/CI)
- Demodulates FM/AM (multi-channel helper), plays audio, and shows live spectrum/waterfall
- Scans ranges with squelch, dwell/hold, auto-logs events, and saves SigMF bundles (IQ + metadata)
- Optionally transcribes voice via Whisper and lets you control/search via a LangChain agent
- Ships with a Regression tab to run end-to-end tests (synthetic/RTL/LLM/Whisper)

## Feature Matrix
| Area | Capabilities |
| --- | --- |
| SDR ingest | RTL-SDR, SoapySDR, file (SigMF), synthetic |
| Demod | FM, AM (multi-channel helper), audio playback |
| Visualization | Spectrum (filled + peak), Waterfall (plasma gradient, full-height seed) |
| Scanning | Dwell/hold, squelch, auto-detect, bundles per event |
| Logging | CSV/JSONL logs + SigMF bundle (IQ + meta + hashes) |
| AI/LLM | Whisper STT (optional), LangChain agent (tune/scan/search/summarize) |
| Regression | Synthetic/RTL probe, scan power, multi-demod, Whisper/LLM smoke tests |
| Plugins | Playbooks, Summaries, Regression runner; extensible plugin loader |

## Quick Start
1. Clone and create a venv:
   ```bash
   git clone <repo_url> astrotrace
   cd astrotrace
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
2. (macOS, optional) Install SDR libs/drivers:
   ```bash
   brew install rtl-sdr soapysdr portaudio  # portaudio only if you want PyAudio
   ```
3. Run the app:
   ```bash
   python main.py
   ```
4. No hardware? Set source to `synthetic` in the UI and click Start to see spectrum/waterfall and hear test bursts.

Audio playback: works if `sounddevice` is present (`pip install sounddevice cffi`). PyAudio is optional and needs portaudio headers.

## Enabling AI/LLM
Set your OpenAI key before launch:
```bash
export OPENAI_API_KEY="sk-..."
```
Then in the UI you can chat with the agent (tune/scan/search/summarize). Whisper transcription can be toggled per run; first model load may take time.

## Regression Tests
- UI: open the “Regression” tab, choose RTL or synthetic, click “Run regression.” Reports land in `test_reports/`.
- CLI: `python -m astrotrace.tests.runner` (uses synthetic if RTL is absent).
- Scenarios: synthetic scan + SigMF bundle, agent tools, RTL probe/scan, multi-demod, Whisper availability (if installed), LLM agent (if `OPENAI_API_KEY` is set). LLM/Whisper scenarios are skipped if unavailable.

## Common Presets (manual today)
- FM broadcast: 88–108 MHz, FM, step 0.2 MHz
- Airband: 118–137 MHz, AM, step 0.025 MHz
- UHF CB (example): 476–478 MHz, NFM, step 0.0125 MHz
(Enter these in scan controls; a Quick Scan preset button is planned.)

## Project Structure
```
core/              scanner, agent, logger, audio_out, sigmf, vector store
SDR/               sdr_ingest, signal_processing
ui/                main_window, widgets, plugin loader
plugins/           playbooks, summaries, regression tab
astrotrace/tests/  regression runner (synthetic/RTL/LLM/Whisper)
runs/, runs_tests/ SigMF bundles (gitignored)
test_reports/      Regression outputs (gitignored)
```

## Roadmap (short)
- More demod/decoders (DMR/P25/etc.)
- Quick Scan presets in UI
- CI for synthetic regression (GitHub Actions included)

## License
MIT License (see LICENSE).

## Contributing
PRs welcome. Please:
- Run regression tests (synthetic) before submitting
- Keep plugins isolated (see `core/plugins.py`)
- Avoid committing `runs/` or `test_reports/`

## Maintainer
**Saman Tabatabaeian**  
Email: <saman.tabatabaeian@gmail.com>  
LinkedIn: [samantabatabaeian](https://www.linkedin.com/in/samantabatabaeian/)

## Support
Issues/PRs on GitHub. For audio: ensure `sounddevice` is installed; for RTL: verify `rtl_test -t` works; for LLM/Whisper: set `OPENAI_API_KEY`.
