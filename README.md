# Open-Source SDR Tool v1

This project is an open-source Software Defined Radio (SDR) receiver and scanner tool. It provides a full-featured SDR application with a cross-platform GUI and introduces advanced capabilities like autonomous frequency scanning and AI-driven speech-to-text transcription of received signals.

## Features

- **Cross-Platform GUI:** Runs on Windows, Linux, macOS (PyQt5). Connect to popular SDR hardware (RTL-SDR, etc.) via SoapySDR or RTL-SDR libraries.  
- **Real-Time Spectrum & Waterfall:** Visualize the radio spectrum in real time. Tune frequency, adjust gain and modulation (AM/FM/SSB/CW) with instant feedback.  
- **DSP Controls:** Set filter bandwidth, squelch level to suppress noise, and enable noise reduction. Record audio from received signals.  
- **Manual Mode:** Tune to a specific frequency and listen/record as with a standard receiver.  
- **Autonomous Scanning Mode:** Define a range or list of frequencies to continuously scan. The tool automatically finds active signals and stops on active channels.  
- **Auto Signal Detection:** Uses a configurable threshold (squelch) to detect when a channel is active. Avoids false alarms by ignoring random spikes.  
- **Signal Logging:** When an active transmission is detected, the tool logs the event with timestamp and frequency (and optional user-defined labels for known frequencies).  
- **Audio Recording:** Active transmissions can be automatically recorded to audio files for later playback.  
- **AI Speech-to-Text (Transcription):** Demodulated voice audio is fed to an integrated Whisper AI engine to transcribe speech. The text is displayed live and saved to the log, enabling quick review and search through communications.  
- **Event Log Export:** All detected events (time, frequency, transcribed text) are saved to a log file (CSV format). This can be analyzed or filtered externally as needed.  
- **Frequency Presets & Favorites:** Save favorite frequencies or scanning ranges for quick access. (Configuration can be done via a simple UI or config file in v1.)  
- **Modular Design:** The system is built in a modular way – hardware interface, signal processing, scanning logic, transcription, and UI are separate components. This makes it easier to maintain and extend (e.g., adding new demodulation modes or integrating digital decoders in future).  
- **Extensible and Future-Proof:** Designed with future enhancements in mind. For example, cloud connectivity (for remote control or cloud-based processing) can be added without major changes. Performance-critical portions can be optimized or rewritten in lower-level languages (C++/Go) for a commercial-grade version, thanks to clear abstraction boundaries between components.

## Installation

### macOS (zsh) — fastest way to **launch the UI**

System dependencies (Qt + audio/transcription tooling). On macOS, `PyQt5` wheels already bundle Qt, but installing Qt tools via Homebrew can help avoid plugin/runtime issues:

```bash
brew install qt ffmpeg
```

Create and activate a virtualenv, then install the **UI-only** Python deps:

```bash
cd /Users/samantaba/Documents/projects/astrotrace

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements-ui.txt
```

Launch the UI:

```bash
python main.py
```

Tip: if you don’t have SDR hardware/drivers set up yet, set **Source = `synthetic`** in the UI and click Start to see the spectrum/waterfall update.

### Full install (includes SDR + transcription + LangChain)

```bash
cd /Users/samantaba/Documents/projects/astrotrace
source .venv/bin/activate
pip install -r requirements.txt
```

Notes:
- **SoapySDR on macOS**: `SoapySDR` is installed via Homebrew (not pip) in many setups:

```bash
brew install soapysdr
```

- **RTL-SDR support**: you may also need RTL-SDR system drivers/libraries (`librtlsdr`) depending on your setup.
- **LangChain LLM**: the app has an offline fallback; to enable the chat agent with OpenAI, set:

```bash
export OPENAI_API_KEY="your_key_here"
```
