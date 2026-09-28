# FLOODGATE

**Batch short-form video generator.** FLOODGATE takes a library of video clips, music, voiceovers and a logo, and renders many unique, subtitled vertical clips ready for Instagram Reels, TikTok and YouTube Shorts. It can also cut long videos and podcasts into short clips.

Each render picks random source material and random timestamps, so a single asset library produces a steady stream of distinct videos without manual editing.

Built with Python, CustomTkinter and FFmpeg. Developed and used on Windows.

---

## Templates

### Sad Clip / Happy Clip

Every render follows a fixed two-act structure:

| Segment | Video | Audio | Caption |
|---|---|---|---|
| **Act A** | Random excerpt from the Act A video pool | Random excerpt from the Act A music pool, mixed under the clip's own audio | Act A caption |
| **Act B** | Random excerpt from the Act B video pool (original audio muted) | Random excerpt from the Act B music pool | Act B caption |
| **Outro** | Logo centered on black | Random voiceover clip; the outro lasts exactly as long as the voiceover | none |

Each act is half of the selected clip length, so the finished video is the clip length plus the voiceover.

### Longform Clips

Cuts short clips out of long videos, podcasts, interviews or shows added to the **Longform Source** slot:

| Segment | Content |
|---|---|
| **Excerpt** | A random excerpt of up to the selected clip length. When the source has been transcribed, it starts at the beginning of a sentence and ends at the end of one, so nobody is cut off mid-sentence. |
| **Framing** | Video is fitted to the output format over a blurred, zoomed copy of itself, so a 16:9 source fills a 9:16 frame. Audio-only sources are shown over an animated waveform. |
| **Outro** | Logo and voiceover, as above, when both a logo and voiceover clips are set. Otherwise the clip ends with the excerpt. |

Output files are named `longform_NNN__<source>__<MMmSSs>.mp4`, where the time is where the excerpt starts in the source.

### Render pipeline

1. **Normalize.** Every source is re-encoded to the same spec (target resolution and frame rate, H.264 / yuv420p, AAC stereo 44.1 kHz) so the segments join cleanly. Clips shorter than the requested duration are skipped where possible, and a clip that fails to decode is retried with a different one.
2. **Caption.** Act captions are burned in with FFmpeg `drawtext`, centered and wrapped to about 28 characters per line.
3. **Mix.** Music is mixed under each act at the configured volume.
4. **Outro.** The logo frame is generated and the voiceover attached.
5. **Concatenate.** The segments are joined into one file in `output/`.
6. **Subtitle.** Spoken words are transcribed and burned in, and an `.srt` file is saved next to the clip. See [Subtitles](#subtitles).

The remixer runs as a separate process, so the interface stays responsive and shows progress live in the Output Log.

---

## Features

- **Asset library.** Dedicated slots for Act A and Act B video, Act A and Act B music, longform sources, voiceovers and a logo. Files under 200 MB are copied into `assets/`; larger files are referenced where they are.
- **Output formats.** 12 presets, including Reel/TikTok 9:16, Square 1:1, Widescreen 16:9, Cinematic 21:9 and Pinterest 2:3, plus custom width, height and FPS. Your own format and length presets are saved to `config.json`.
- **Clip length.** Choose from 2 seconds to 5 minutes, or save your own lengths.
- **Projects.** Each project keeps its own asset pools, captions and render settings. Switch between them from the top bar.
- **Automatic subtitles.** Every render is subtitled automatically. Any other video or audio file can be subtitled from the Subtitles panel. See [Subtitles](#subtitles).
- **Browse gallery.** Review rendered clips with favorites, color-coded tags, folders, search, and sorting by date, favorites or name.
- **Trash.** Deleted clips go to a trash folder, where they can be restored or permanently deleted.
- **Upload queue.** Queue clips with captions and export them into a ready-to-post folder. See [Posting](#posting).
- **Batch rendering.** Render up to 100 clips per run. Press **Ctrl+R** from anywhere in the app to start.

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

On first launch, your settings are created from `config.example.json`. Your own `config.json` holds your asset paths, so it is not tracked in git.

## Usage

```bash
python floodgate.py
```

1. On the **Assets** tab, choose a template, then add clips to its slots and select a logo.
2. Set the captions, caption font, music volume, output format, clip length and number of renders.
3. Click **Run Remixer** or press **Ctrl+R**. Progress appears in the Output Log.
4. Review the results on the **Browse** tab. Rendered files are saved to `output/`.

You can also run the remixer on its own. It reads the current `config.json`:

```bash
python remixer.py
```

Press **F11** to toggle full screen.

---

## Subtitles

Speech is transcribed locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper), an optimized build of OpenAI's Whisper model. It is free, runs offline, and keeps your media on your machine.

**Automatic (every render):** with **Auto-subtitle every render** checked in the Subtitles panel (on by default), each clip gets subtitles in the chosen style, plus an `.srt` next to it.
- **Sad Clip / Happy Clip:** speech in the Act A clip and the voiceover outro is subtitled. Act B is muted, so it has none.
- **Longform Clips:** the whole source is transcribed once, and each clip's subtitles come from that saved transcript.
- If a clip has no speech, or subtitles can't be made (for example, faster-whisper isn't installed), the render still completes without them.

**Any file:** click **Subtitle a video…** in the Subtitles panel and pick a file. The subtitled video and its `.srt` are saved to `output/` and appear in the Browse tab.

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
| `--model` | `tiny`, `base`, `small` (default), `medium`, `large-v3-turbo`, `large-v3`. Larger models are more accurate but slower. `large-v3-turbo` is the best choice for noisy audio: close to `large-v3` accuracy at a fraction of the time. The app's Fast, Balanced, Accurate and Best map to `base`, `small`, `medium` and `large-v3-turbo`. |
| `--language` | A language code such as `en` or `es`. Detected automatically by default. |
| `--font` | Subtitle font. Defaults to the caption font set in the app. |

**How it works:**
- The first time you use a model, it is downloaded once, about 150 MB (Fast) to 1.6 GB (Best).
- Whole files are transcribed once with word-level timestamps and cached in `transcripts/`. Cutting more clips from the same podcast, or re-rendering in another style, reuses the transcript.
- An NVIDIA GPU is used automatically if the CUDA 12 libraries (cuBLAS and cuDNN 9) are installed. Otherwise transcription runs on the CPU, which needs no setup but is slower. On a CPU, **Balanced** is a good choice for large batches and **Best** for noisy clips.
- Audio-only files are rendered at 1080×1920 over an animated waveform.

---

## Posting

On the **Browse** tab, click **↑** on a clip and enter its caption (text, hashtags, mentions) to add it to the Upload queue. The queue is saved between sessions.

On the **Upload** tab:
- **Export All** copies every queued clip into a new dated folder in `exports/`. Each clip gets a matching `.txt` caption and `.srt` subtitles, and the folder has a `captions.txt` listing them all. The folder opens when the export finishes, ready to post from your phone or browser.
- **Copy Caption** puts the selected clip's caption on the clipboard.
- **Open Exports** opens the exports folder.

Posting directly to Instagram or TikTok requires developer API access from Meta and TikTok and is not built yet.

---

## Project layout

| Path | Purpose |
|---|---|
| `floodgate.py` | Application entry point: window, projects, formats, templates, upload queue and job launching |
| `ui_assets.py` | Assets tab: asset slots, settings, render and subtitle controls, log panel |
| `ui_browse.py` | Browse tab: gallery, filtering, tags, folders and trash |
| `core.py` | Shared constants, presets, clip metadata, project storage and the upload queue |
| `remixer.py` | FFmpeg rendering pipeline for both templates |
| `subtitles.py` | Speech transcription and subtitle rendering (usable on its own) |
| `config.example.json` | Default settings used to create `config.json` |
| `make_changelog.py` | Regenerates `FLOODGATE_Whitepaper.html` from the git history |

Created while the app runs (not tracked in git): `config.json`, `assets/`, `output/`, `trash/`, `projects/`, `transcripts/`, `exports/`, `clip_meta.json`, `upload_queue.json`.

---

## Status and roadmap

| Area | Status |
|---|---|
| Sad Clip / Happy Clip and Longform Clips rendering | Working |
| Automatic subtitles | Working |
| Asset management, projects, browse gallery, trash | Working |
| Upload queue | Exports ready-to-post folders. Direct posting to Instagram/TikTok is not built yet. |
| Preview Mode setting | Not used yet. Output resolution comes from the selected format. |

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
