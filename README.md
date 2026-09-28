# FLOODGATE

**Batch short-form video generator.** FLOODGATE takes a library of video clips, music, voiceovers and a logo, and renders many unique, captioned vertical clips ready for Instagram Reels, TikTok and YouTube Shorts.

Each render picks random source clips and random timestamps, so a single asset library produces a steady stream of distinct videos without manual editing.

Built with Python, CustomTkinter and FFmpeg. Developed and used on Windows.

---

## How it works

Every render follows a fixed two-act structure:

| Segment | Video | Audio | Caption |
|---|---|---|---|
| **Act A** | Random excerpt from the Act A video pool | Random excerpt from the Act A music pool, mixed under the clip's own audio | Act A caption |
| **Act B** | Random excerpt from the Act B video pool (original audio muted) | Random excerpt from the Act B music pool | Act B caption |
| **Outro** | Logo centered on black | Random voiceover clip; the outro lasts exactly as long as the voiceover | none |

Each act is half of the selected clip length, so the finished video is the clip length plus the voiceover.

### Render pipeline

1. **Normalize.** Every source is re-encoded to the same spec (target resolution and frame rate, H.264 / yuv420p, AAC stereo 44.1 kHz) so the segments join cleanly. Clips shorter than the requested duration are skipped where possible, and a clip that fails to decode is retried with a different one.
2. **Caption.** Captions are burned in with FFmpeg `drawtext`, centered and wrapped to about 28 characters per line.
3. **Mix.** Music is mixed under each act at the configured volume.
4. **Outro.** The logo frame is generated and the voiceover attached.
5. **Concatenate.** The three segments are joined into `output/flood_NNN__<actA>__<actB>.mp4`.

The remixer runs as a separate process, so the interface stays responsive and shows the remixer's output live in the built-in log panel.

---

## Features

- **Asset library.** Dedicated slots for Act A and Act B video, Act A and Act B music, voiceovers and a logo. Files under 200 MB are copied into `assets/`; larger files are referenced where they are.
- **Output formats.** 12 presets, including Reel/TikTok 9:16, Square 1:1, Widescreen 16:9, Cinematic 21:9 and Pinterest 2:3, plus custom width, height and FPS. Your own format and length presets are saved to `config.json`.
- **Clip length.** Choose from 2 seconds to 5 minutes, or save your own lengths.
- **Projects.** Each project keeps its own asset pools, captions and render settings. Switch between them from the top bar.
- **Browse gallery.** Review rendered clips with favorites, color-coded tags, folders, search, and sorting by date, favorites or name.
- **Trash.** Deleted clips go to a trash folder, where they can be restored or permanently deleted.
- **Batch rendering.** Render up to 100 clips per run. Press **Ctrl+R** from anywhere in the app to start.
- **Automatic subtitles.** Transcribe any video or audio file (a full podcast, interview or video) and burn in styled captions, plus an `.srt` file for platforms that accept uploaded captions. See [Subtitles](#subtitles).

---

## Requirements

- Python 3.10 or later, with Tkinter (included with the standard Windows and macOS installers)
- [FFmpeg](https://ffmpeg.org/download.html) (`ffmpeg` and `ffprobe`)
- The Python packages listed in `requirements.txt`

FLOODGATE looks for FFmpeg on your `PATH` first, then in `C:\ffmpeg\bin\`.

## Installation

```bash
git clone https://github.com/djfloood-ctrl/floodgate.git
cd floodgate
pip install -r requirements.txt
```

## Usage

```bash
python floodgate.py
```

1. On the **Assets** tab, add clips to each slot and select a logo.
2. Set the captions, caption font, music volume, output format, clip length and number of renders.
3. Click **Run Remixer** or press **Ctrl+R**. Progress appears in the Remixer Log.
4. Review the results on the **Browse** tab. Rendered files are saved to `output/`.

You can also run the remixer on its own. It reads the current `config.json`:

```bash
python remixer.py
```

Press **F11** to toggle full screen.

---

## Subtitles

FLOODGATE can add subtitles to any video or audio file. Speech is transcribed locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper), an optimized build of OpenAI's Whisper model. It is free, runs offline, and keeps your media on your machine.

**In the app:** on the Assets tab, open the **Subtitles** panel, choose a style and accuracy level, then click **Subtitle a video** and pick a file. Progress appears in the Output Log. The subtitled video and its `.srt` file are saved to `output/` and appear in the Browse tab.

**From the command line:**

```bash
python subtitles.py "Episode 12.mp4"                                  # pop style, whole file
python subtitles.py "Episode 12.mp4" --style classic                  # classic bottom-line captions
python subtitles.py "Episode 12.mp4" --start 754 --end 812 -o clip.mp4  # just one excerpt
python subtitles.py interview.mp3                                     # audio-only: rendered over a waveform
python subtitles.py "Episode 12.mp4" --srt-only                       # captions file only, no video
```

| Option | Values |
|---|---|
| `--style` | `pop`: up to three large words at a time, with the spoken word highlighted. `classic`: sentence captions along the bottom. |
| `--model` | `tiny`, `base`, `small` (default), `medium`, `large-v3`. Larger models are more accurate but slower. The app's Fast, Balanced and Most accurate map to `base`, `small` and `medium`. |
| `--language` | A language code such as `en` or `es`. Detected automatically by default. |
| `--font` | Subtitle font. Defaults to the caption font set in the app. |

**How it works:**
- The first time you use a model, it is downloaded once, about 150–1500 MB depending on size.
- Each file is transcribed once with word-level timestamps and cached in `transcripts/`. Cutting more clips from the same podcast, or re-rendering in another style, reuses the transcript and only takes as long as the video encode.
- An NVIDIA GPU is used automatically if the CUDA 12 libraries (cuBLAS and cuDNN 9) are installed. Otherwise transcription runs on the CPU, which needs no setup but is slower.
- Audio-only files are rendered at 1080×1920 over an animated waveform.

---

## Project layout

| Path | Purpose |
|---|---|
| `floodgate.py` | Application entry point: window, projects, formats, templates and launching the remixer |
| `ui_assets.py` | Assets tab: asset slots, settings, render controls and log panel |
| `ui_browse.py` | Browse tab: gallery, filtering, tags, folders and trash |
| `core.py` | Shared constants, presets, clip metadata and project storage |
| `remixer.py` | FFmpeg rendering pipeline |
| `subtitles.py` | Speech transcription and subtitle rendering (usable on its own) |
| `config.json` | Current asset lists and render settings |
| `make_changelog.py` | Regenerates `FLOODGATE_Whitepaper.html` from the git history |

Created while the app runs (not tracked in git): `assets/`, `output/`, `trash/`, `projects/`, `transcripts/`, `clip_meta.json`.

---

## Status and roadmap

| Area | Status |
|---|---|
| Sad Clip / Happy Clip rendering | Working |
| Asset management, projects, browse gallery, trash | Working |
| **Longform Clips** template | UI only. The remixer does not render it yet and reports this when you run it. |
| **Upload** tab (Instagram / TikTok) | Placeholder. Pairing and uploading are not connected to either platform yet. |
| Preview Mode setting | Not used yet. Output resolution comes from the selected format. |

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
