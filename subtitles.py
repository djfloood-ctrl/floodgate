"""
subtitles.py – Automatic subtitles for FloodGate

Transcribes speech with faster-whisper (runs locally; the model downloads once
on first use), caches word-level timestamps per source file, and burns styled
subtitles into the video. Also writes an .srt next to the output.

Usage:
  python subtitles.py VIDEO_OR_AUDIO [--style pop|classic] [--model small]
                      [--language en] [--start SECS] [--end SECS]
                      [--font Impact] [--srt-only] [-o OUTPUT.mp4]

Audio-only inputs (podcasts) are rendered over an animated waveform.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from remixer import FFMPEG, FFPROBE

# Keep the app's log readable: no \r progress bars, symlink or token warnings.
# huggingface_hub reads these once at import, so set them before faster-whisper loads.
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")

BASE_DIR       = Path(__file__).parent
CONFIG_PATH    = BASE_DIR / "config.json"
OUTPUT_DIR     = BASE_DIR / "output"
TRANSCRIPT_DIR = BASE_DIR / "transcripts"

MODELS = ["tiny", "base", "small", "medium", "large-v3-turbo", "large-v3"]
STYLES = ["pop", "classic"]

# ASS colours are &HAABBGGRR
WHITE     = "&H00FFFFFF"
BLACK     = "&H00000000"
HIGHLIGHT = "&H0000E5FF"   # warm yellow
SHADOW    = "&H80000000"

AUDIO_ONLY_SIZE = (1080, 1920)


# ─────────────────────────────────────────────
#  Probing
# ─────────────────────────────────────────────

def probe(path):
    """Return duration and the first video stream's size (None if audio-only)."""
    result = subprocess.run(
        [FFPROBE, "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe could not read {path}: {result.stderr.strip()}")
    info = json.loads(result.stdout)
    video = next((s for s in info.get("streams", [])
                  if s.get("codec_type") == "video"
                  and not s.get("disposition", {}).get("attached_pic")), None)
    duration = float(info.get("format", {}).get("duration") or 0)
    size = None
    if video:
        size = (int(video["width"]), int(video["height"]))
        # Phones store portrait video sideways plus a rotation flag; ffmpeg applies
        # the rotation when decoding, so lay the subtitles out for the upright frame.
        rotation = video.get("tags", {}).get("rotate") or next(
            (sd.get("rotation") for sd in video.get("side_data_list", []) if "rotation" in sd), 0)
        if abs(int(float(rotation))) % 180 == 90:
            size = (size[1], size[0])
    return duration, size


# ─────────────────────────────────────────────
#  Transcription (cached)
# ─────────────────────────────────────────────

def _cache_path(src, model, language):
    st = Path(src).stat()
    key = f"{Path(src).resolve()}|{st.st_size}|{int(st.st_mtime)}|{model}|{language or 'auto'}"
    return TRANSCRIPT_DIR / f"{Path(src).stem[:40]}_{hashlib.sha1(key.encode()).hexdigest()[:12]}.json"


def transcribe(src, model="small", language=None, log=print):
    """
    Transcribe the whole file once and cache it, so any number of clips
    cut from the same podcast or interview reuse the same transcript.
    Returns {"language": str, "words": [{"w": str, "s": float, "e": float}, ...]}.
    """
    cache = _cache_path(src, model, language)
    if cache.exists():
        with open(cache, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("words"):
            log(f"📝 Using cached transcript ({cache.name})")
            return data
        cache.unlink()  # an empty transcript is never worth reusing

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        log("❌ Subtitles need the faster-whisper package.")
        log("   Install it with:  py -m pip install faster-whisper")
        sys.exit(2)

    duration, _ = probe(src)
    log(f"🧠 Loading Whisper model '{model}' (downloads once on first use)...")
    try:
        whisper = _load_model(WhisperModel, model, "auto")
        log(f"🎙️  Transcribing {Path(src).name} ({duration / 60:.1f} min)...")
        words, info = _transcribe_with_retry(whisper, src, language, duration, log)
    except RuntimeError as e:
        # An NVIDIA GPU without the CUDA libraries (cuBLAS/cuDNN) fails only once
        # transcription starts, so retry the whole pass on the CPU.
        if not re.search(r"cuda|cublas|cudnn", str(e), re.IGNORECASE):
            raise
        log("⚠️  GPU libraries not available — using the CPU instead (slower).")
        whisper = _load_model(WhisperModel, model, "cpu")
        log(f"🎙️  Transcribing {Path(src).name} ({duration / 60:.1f} min)...")
        words, info = _transcribe_with_retry(whisper, src, language, duration, log)

    data = {"language": info.language, "model": model, "source": str(src), "words": words}
    if words:
        TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    log(f"✅ Transcribed {len(words)} words (language: {info.language})")
    return data


def _load_model(WhisperModel, model, device):
    """Use the downloaded copy when there is one (no network, no Hub warnings); otherwise download it."""
    try:
        return WhisperModel(model, device=device, compute_type="int8", local_files_only=True)
    except FileNotFoundError:
        return WhisperModel(model, device=device, compute_type="int8")


def _transcribe_with_retry(whisper, src, language, duration, log):
    """
    The voice-activity filter skips silence, which speeds up podcasts, but it can
    throw away shouted or emotional speech over loud music or crowds. If it leaves
    nothing, transcribe the full audio instead.
    """
    words, info = _run_whisper(whisper, src, language, duration, log, vad=True)
    if not words:
        log("⚠️  No speech detected with the voice filter — retrying on the full audio...")
        words, info = _run_whisper(whisper, src, language, duration, log, vad=False)
    return words, info


def _run_whisper(whisper, src, language, duration, log, vad=True):
    segments, info = whisper.transcribe(
        str(src), language=language, word_timestamps=True, vad_filter=vad)
    words, last_pct = [], -10
    for seg in segments:
        for w in seg.words or []:
            text = w.word.strip()
            if text:
                words.append({"w": text, "s": round(w.start, 3), "e": round(max(w.end, w.start + 0.05), 3)})
        pct = int(100 * seg.end / duration) if duration else 100
        if pct >= last_pct + 10:
            log(f"         → {min(pct, 100)}%")
            last_pct = pct
    return words, info


def words_between(words, start=0.0, end=None):
    """Words inside [start, end), re-timed so the excerpt starts at 0."""
    out = []
    for w in words:
        if w["e"] <= start or (end is not None and w["s"] >= end):
            continue
        s = max(w["s"], start) - start
        e = (min(w["e"], end) if end is not None else w["e"]) - start
        out.append({"w": w["w"], "s": s, "e": max(e, s + 0.05)})
    return out


# ─────────────────────────────────────────────
#  Grouping words into on-screen chunks
# ─────────────────────────────────────────────

SENTENCE_END = re.compile(r"[.!?…]$")


def chunk_words(words, max_words, max_chars, max_gap):
    chunks, cur = [], []
    for w in words:
        if cur:
            gap = w["s"] - cur[-1]["e"]
            chars = sum(len(x["w"]) + 1 for x in cur) + len(w["w"])
            if (len(cur) >= max_words or chars > max_chars or gap > max_gap
                    or SENTENCE_END.search(cur[-1]["w"])):
                chunks.append(cur)
                cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    return chunks


def chunk_times(chunks, hold=0.4):
    """
    Keep each chunk up until the next one starts when the pause is shorter than
    `hold` seconds (so text doesn't flicker), and never let two chunks overlap.
    """
    times = []
    for i, c in enumerate(chunks):
        end = c[-1]["e"]
        if i + 1 < len(chunks):
            nxt = chunks[i + 1][0]["s"]
            if nxt - end < hold:
                end = nxt
        times.append((c[0]["s"], end))
    return times


# ─────────────────────────────────────────────
#  Subtitle formats
# ─────────────────────────────────────────────

def _ass_time(t):
    cs = int(round(max(t, 0) * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _srt_time(t):
    ms = int(round(max(t, 0) * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def _ass_escape(text):
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def _pop_token(word):
    # Big caption style: upper-case, drop trailing commas/periods but keep ? and !
    return re.sub(r"[,.;:]+$", "", word).upper()


def build_ass(words, style, width, height, font):
    base = min(width, height)
    if style == "pop":
        size, margin_v, outline = round(base * 0.075), round(height * 0.22), max(3, round(base * 0.006))
        chunks = chunk_words(words, max_words=3, max_chars=18, max_gap=0.6)
    else:
        size, margin_v, outline = round(base * 0.05), round(height * 0.06), max(2, round(base * 0.003))
        chunks = chunk_words(words, max_words=12, max_chars=42, max_gap=1.0)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},{WHITE},{HIGHLIGHT},{BLACK},{SHADOW},-1,0,0,0,100,100,0,0,1,{outline},{max(1, outline // 2)},2,{round(width * 0.06)},{round(width * 0.06)},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for chunk, (c_start, c_end) in zip(chunks, chunk_times(chunks)):
        if style == "pop":
            tokens = [_ass_escape(_pop_token(w["w"])) for w in chunk]
            # One event per spoken word, with that word highlighted and slightly enlarged
            for i, w in enumerate(chunk):
                start = c_start if i == 0 else w["s"]
                end = chunk[i + 1]["s"] if i + 1 < len(chunk) else c_end
                if end <= start:
                    continue
                text = " ".join(
                    f"{{\\c{HIGHLIGHT}\\fscx112\\fscy112}}{t}{{\\c{WHITE}\\fscx100\\fscy100}}" if j == i else t
                    for j, t in enumerate(tokens))
                lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{text}")
        else:
            text = _ass_escape(" ".join(w["w"] for w in chunk))
            lines.append(f"Dialogue: 0,{_ass_time(c_start)},{_ass_time(c_end)},Default,,0,0,0,,{text}")
    return header + "\n".join(lines) + "\n"


def build_srt(words):
    chunks = chunk_words(words, max_words=12, max_chars=42, max_gap=1.0)
    out = []
    for n, (chunk, (s, e)) in enumerate(zip(chunks, chunk_times(chunks)), 1):
        out.append(f"{n}\n{_srt_time(s)} --> {_srt_time(e)}\n{' '.join(w['w'] for w in chunk)}\n")
    return "\n".join(out)


# ─────────────────────────────────────────────
#  Rendering
# ─────────────────────────────────────────────

def burn(src, ass_path, out, size, start=0.0, duration=None):
    """
    Burn subtitles into `src`. ffmpeg runs inside the subtitle file's folder and
    references it by name, which sidesteps filter-path escaping on Windows.
    """
    trim_in = ["-ss", f"{start:.3f}"] if start else []
    trim_out = ["-t", f"{duration:.3f}"] if duration else []
    sub_filter = f"subtitles={Path(ass_path).name}"

    if size:
        cmd = [FFMPEG, "-y", *trim_in, "-i", str(Path(src).resolve()), *trim_out,
               "-vf", sub_filter,
               "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "192k", str(Path(out).resolve())]
    else:
        w, h = AUDIO_ONLY_SIZE
        graph = (f"[0:a]showwaves=s={w}x{h // 4}:mode=cline:rate=30:colors=0xFF4444[wave];"
                 f"color=c=0x1A1A1A:s={w}x{h}:r=30[bg];"
                 f"[bg][wave]overlay=0:(H-h)/2:shortest=1,{sub_filter},format=yuv420p[v]")
        cmd = [FFMPEG, "-y", *trim_in, "-i", str(Path(src).resolve()), *trim_out,
               "-filter_complex", graph, "-map", "[v]", "-map", "0:a",
               "-c:v", "libx264", "-preset", "fast", "-crf", "20",
               "-c:a", "aac", "-b:a", "192k", "-shortest", str(Path(out).resolve())]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path(ass_path).parent))
    if result.returncode != 0:
        tail = "\n".join(result.stderr.strip().splitlines()[-8:])
        raise RuntimeError(f"ffmpeg failed while burning subtitles:\n{tail}")


def subtitle_file(src, style="pop", model="small", language=None, font="Arial",
                  start=0.0, end=None, srt_only=False, output=None, log=print):
    """Transcribe (or reuse the cached transcript) and write the subtitled video + .srt."""
    src = Path(src)
    duration, size = probe(src)
    end = min(end, duration) if end else None
    if start and start >= (end or duration):
        raise ValueError("--start must be before the end of the clip")

    transcript = transcribe(src, model=model, language=language, log=log)
    words = words_between(transcript["words"], start or 0.0, end)
    if not words:
        log("⚠️  No speech found in that range — nothing to subtitle.")
        return None

    out = Path(output) if output else OUTPUT_DIR / f"{src.stem[:60]}_subs.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    srt = out.with_suffix(".srt")
    srt.write_text(build_srt(words), encoding="utf-8")
    log(f"📄 Subtitles saved → {srt.name}")
    if srt_only:
        return srt

    w, h = size or AUDIO_ONLY_SIZE
    ass = TRANSCRIPT_DIR / f"_{out.stem}.ass"
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    ass.write_text(build_ass(words, style, w, h, font), encoding="utf-8")
    kind = "video" if size else "audio → waveform video"
    log(f"🔥 Burning '{style}' subtitles ({kind}, {w}x{h})...")
    try:
        burn(src, ass, out, size, start or 0.0, (end - (start or 0.0)) if end else None)
    finally:
        ass.unlink(missing_ok=True)
    log(f"✅ Done → {out.name}")
    return out


def _default_font():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("caption_font", "Arial")
    except (OSError, ValueError):
        return "Arial"


def main(argv=None):
    p = argparse.ArgumentParser(description="Automatic subtitles for any video or audio file.")
    p.add_argument("input", help="video or audio file (podcast, interview, movie...)")
    p.add_argument("--style", choices=STYLES, default="pop",
                   help="pop: big 3-word captions with the spoken word highlighted; classic: bottom lines")
    p.add_argument("--model", choices=MODELS, default="small",
                   help="Whisper model: bigger is more accurate but slower (default: small)")
    p.add_argument("--language", default=None, help="language code such as en or es (default: auto-detect)")
    p.add_argument("--font", default=None, help="subtitle font (default: the caption font in config.json)")
    p.add_argument("--start", type=float, default=0.0, help="excerpt start, in seconds")
    p.add_argument("--end", type=float, default=None, help="excerpt end, in seconds")
    p.add_argument("--srt-only", action="store_true", help="only write the .srt file, don't render video")
    p.add_argument("-o", "--output", default=None, help="output .mp4 (default: output/<name>_subs.mp4)")
    a = p.parse_args(argv)

    if not Path(a.input).exists():
        print(f"❌ File not found: {a.input}")
        return 1
    try:
        result = subtitle_file(a.input, style=a.style, model=a.model, language=a.language,
                               font=a.font or _default_font(), start=a.start, end=a.end,
                               srt_only=a.srt_only, output=a.output)
    except (RuntimeError, ValueError) as e:
        print(f"❌ {e}")
        return 1
    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())
