# FLOODGATE — Changelog

---

## Unreleased

### Automatic subtitles
- New `subtitles.py`: transcribes any video or audio file locally with faster-whisper and burns in styled subtitles
- Two styles: **Pop**, up to three large words at a time with the spoken word highlighted, and **Classic**, sentence captions along the bottom
- Also writes an `.srt` captions file; an option creates only the `.srt`
- Transcripts are cached per file, so re-cutting the same podcast or interview is fast
- Excerpt support with `--start` and `--end`; audio-only files are rendered over a waveform
- New Subtitles panel on the Assets tab; the log panel is renamed Output Log and shows subtitle progress
- Only one job, render or subtitles, runs at a time
- Accuracy levels: Fast, Balanced, Accurate and Best. Best uses Whisper large-v3-turbo and is the most accurate on noisy audio

### Fixes
- Projects keep independent settings; switching projects no longer carries format, volume, or other settings from the previous project
- Longform source assets are saved per project
- Remixer respects the minimum clip length on retries and names output files after the clips actually used
- Remixer locates FFmpeg on `PATH`, falling back to `C:\ffmpeg\bin`
- Remixer reports that the Longform Clips template is not yet supported instead of rendering the wrong template
- A second render can no longer be started while one is running
- Custom format dialog validates width, height, and FPS
- User-defined format and length presets persist across restarts
- Missing asset files no longer prevent the app from starting
- Added README and `requirements.txt`; whitepaper updated to reflect current behavior

---

## v2.3 — 2026-06-24

- Integrated remixer log viewer with live output
- Per-folder sort in the Browse gallery
- Codebase split into `core`, `ui_assets`, and `ui_browse` modules

---

## v2.2 — 2026-06-04

- Updated whitepaper with technical accuracy and DJ FLOOD voice
- Removed build artifacts, installer files, and patch notes from repo
- Removed unused fix and cleanup scripts — repo cleaned to production state

---

## v2.1 — 2026-05-12

- Format and length preset save/remove buttons with template persistence in config
- Length selector rebuilt: 2s–5min options, clip duration reads from config, global override, minimum duration check
- Template switcher: SAD CLIP / HAPPY CLIP and LONGFORM CLIPS with working dropdown
- 12 format presets covering all major aspect ratios, Custom popup dialog with W/H/FPS inputs, default to Reel/TikTok (9:16)
- Momentum scrolling: 2x base speed, accelerates to 4x on fast scroll, decelerates, unified across all tabs and listboxes
- Larger subtitles, lighter color, descriptive content type hints in asset slots
- Equal 50/50 column widths, even padding throughout UI, filename truncation on long names
- 4 browse cards per row at fixed 180×210, asset panels with side padding
- Global mousewheel scrolling on all tabs, CTkScrollableFrame on browse gallery
- Scrolling enabled on assets panel, browse sidebar, and upload queue
- Remixer updated to read format and length from config

---

## v2.0 — 2026-05-11

- In-place browse filtering introduced — folder, tag, and search filters operate on live widgets without a full rebuild
- Refresh button is the only trigger for a complete gallery rebuild
- Instant star toggle — no page reload on favorites interaction, favorites folder refreshes correctly on un-star
- Live render polling — browse auto-updates every 1.5s during active render, auto-stops on completion
- Instant trash — card removed from gallery immediately on delete, no delay
- Trash icon, views label, and favorites fix
- Working base established: CustomTkinter UI fully converted from standard tkinter

---

*FLOODGATE — Python, CustomTkinter and FFmpeg.*
