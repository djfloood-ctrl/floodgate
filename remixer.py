import json
import os
import shutil
import subprocess
import tempfile
import sys
import random
from pathlib import Path

# ─────────────────────────────────────────────
#  REMIXER AGENT v5.2 — THE FLOOD FORMULA
#
#  - Normalizes every asset before processing
#    (fixes M4A, MOV, H.265, format mismatches)
#  - All segments rendered to identical spec
#    before concat — no more lag or audio bleed
#  - Outro duration matches voiceover exactly
#  - Act B video audio muted
#  - Consistent captions, no 'n' bug
# ─────────────────────────────────────────────

BASE_DIR   = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"


def find_tool(name):
    """Prefer the tool on PATH; fall back to the classic C:\ffmpeg install."""
    found = shutil.which(name)
    if found:
        return found
    fallback = Path(r"C:\ffmpeg\bin") / f"{name}.exe"
    return str(fallback) if fallback.exists() else name


FFMPEG     = find_tool("ffmpeg")
FFPROBE    = find_tool("ffprobe")

# Will be set from config in main()
CLIP_DURATION = 4.5  # Will be overridden in main()

TARGET_AR     = "44100"  # audio sample rate
TARGET_AC     = "2"      # stereo


def load_config():
    if not CONFIG_PATH.exists():
        print("⚠️  config.json not found. Open FLOODGATE once to create it,")
        print("   or copy config.example.json to config.json.")
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve(path):
    return str(BASE_DIR / path) if not Path(path).is_absolute() else path


def check_assets(config, longform=False):
    keys = (["longform_source", "voiceover_clips"] if longform else
            ["act_a_videos", "act_b_videos", "act_a_music", "act_b_music", "voiceover_clips"])
    missing = []
    for key in keys:
        for path in config.get(key, []):
            if not Path(resolve(path)).exists():
                missing.append(resolve(path))
    if config.get("logo") and not Path(resolve(config["logo"])).exists():
        missing.append(resolve(config["logo"]))
    if missing:
        print("\n⚠️  Missing assets:")
        for m in missing:
            print(f"   {m}")
        sys.exit(1)
    if longform and not config.get("longform_source"):
        print("⚠️  No longform sources found. Add a video or podcast to the Longform Source slot.")
        sys.exit(1)
    if not longform and not config.get("voiceover_clips"):
        print("⚠️  No voiceover clips found.")
        sys.exit(1)
    print("✅ All assets found.\n")


def run(cmd, cwd=None):
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    # Only return actual errors, not FFmpeg build info
    stderr = result.stderr
    # Filter out the repetitive NAL unit errors
    lines = [l for l in stderr.split('\n') if 'Invalid NAL' not in l and 'Error submitting packet' not in l and 'channel element' not in l]
    return result.returncode == 0, '\n'.join(lines)


def get_duration(path):
    cmd = [FFPROBE, "-v", "error",
           "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except:
        return None


def normalize_video(src, out, duration, mute=False):
    """
    Extract a random clip AND normalize to a consistent spec in one pass:
    - 1920x1080, H.264, yuv420p, 30fps
    - AAC stereo 44100hz (or silent if mute=True)
    This ensures all segments are byte-compatible before concat.
    """
    total = get_duration(src)
    if total is None or total <= duration:
        start = 0.0
        if total is not None and total < duration:
            print(f"         ⚠ Source is {total:.1f}s, requested {duration:.1f}s — using full clip")
    else:
        start = random.uniform(0, total - duration)

    vf = (
        f"scale={TARGET_W}:{TARGET_H}:"
        f"force_original_aspect_ratio=decrease,"
        f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2,"
        f"fps={TARGET_FPS},"
        f"format=yuv420p"
    )

    if mute:
        # Step 1: Create normalized video with original audio
        tmp_vid = out.replace(".mp4", "_tmpvid.mp4")
        cmd1 = [
            FFMPEG, "-y",
            "-err_detect", "ignore_err",
            "-ss", f"{start:.2f}",
            "-i", src,
            "-t", str(duration),
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-ar", TARGET_AR, "-ac", TARGET_AC,
            tmp_vid
        ]
        ok1, err1 = run(cmd1)
        if not ok1:
            print(f"❌ Normalize video error (step 1): {err1}")
            return False, start

        # Step 2: Replace audio with silence
        cmd2 = [
            FFMPEG, "-y",
            "-i", tmp_vid,
            "-f", "lavfi", "-i", f"anullsrc=r={TARGET_AR}:cl=stereo",
            "-c:v", "copy",
            "-c:a", "aac",
            "-ar", TARGET_AR, "-ac", TARGET_AC,
            "-map", "0:v", "-map", "1:a",
            "-shortest",
            out
        ]
        ok2, err2 = run(cmd2)
        # Clean up temp file
        if os.path.exists(tmp_vid):
            os.remove(tmp_vid)
        if not ok2:
            print(f"❌ Normalize video error (step 2): {err2}")
            return False, start
        return True, start

    else:
        cmd = [
            FFMPEG, "-y",
            "-err_detect", "ignore_err",
            "-ss", f"{start:.2f}",
            "-i", src,
            "-t", str(duration),
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-ar", TARGET_AR, "-ac", TARGET_AC,
            out
        ]
        ok, err = run(cmd)
        if not ok:
            print(f"❌ Normalize video error: {err}")
        return ok, start

def normalize_audio(src, duration, out):
    """
    Extract random audio snippet, normalize to AAC stereo 44100hz.
    Handles MP3, M4A, WAV, AAC — anything FFmpeg can read.
    """
    total = get_duration(src)
    if total is None or total <= duration:
        start = 0.0
        if total is not None and total < duration:
            print(f"         ⚠ Source is {total:.1f}s, requested {duration:.1f}s — using full clip")
    else:
        start = random.uniform(0, total - duration)

    cmd = [
        FFMPEG, "-y",
        "-ss", f"{start:.2f}",
        "-i", src,
        "-t", str(duration),
        "-c:a", "aac",
        "-ar", TARGET_AR, "-ac", TARGET_AC,
        "-vn", out
    ]
    ok, err = run(cmd)
    if not ok:
        print(f"❌ Normalize audio error: {err}")
    return ok, start


def normalize_voice(src, out):
    """Normalize voiceover. Under 6s: play from start. Over 6s: random subsection."""
    total = get_duration(src)
    if total is None or total <= 6:
        # Use full clip from beginning
        cmd = [
            FFMPEG, "-y",
            "-i", src,
            "-c:a", "aac",
            "-ar", TARGET_AR, "-ac", TARGET_AC,
            "-vn", out
        ]
    else:
        start = random.uniform(0, total - 6)
        cmd = [
            FFMPEG, "-y",
            "-ss", f"{start:.2f}",
            "-i", src,
            "-t", "6",
            "-c:a", "aac",
            "-ar", TARGET_AR, "-ac", TARGET_AC,
            "-vn", out
        ]
    ok, err = run(cmd)
    if not ok:
        print(f"❌ Voice normalize error: {err}")
    return ok


def add_caption(video_in, text, video_out, caption_font="Impact"):
    """
    Burn centered caption with custom font.
    Each line is a separate drawtext to avoid the literal 'n' bug.
    """
    words = text.split()
    lines, current = [], ""
    for word in words:
        if len(current) + len(word) + 1 > 28:
            lines.append(current.strip())
            current = word
        else:
            current += " " + word
    if current:
        lines.append(current.strip())

    fontsize    = 72
    line_height = fontsize + 14
    total_h     = len(lines) * line_height
    start_y     = f"(h-{total_h})/2"

    filter_parts = []
    for i, line in enumerate(lines):
        safe = line.replace("'", "\u2019").replace("\\", "").replace(":", " ")
        y    = f"({start_y}+{i * line_height})"
        filter_parts.append(
            f"drawtext=text='{safe}':"
            f"fontsize={fontsize}:fontcolor=white:"
            f"borderw=4:bordercolor=black:"
            f"x=(w-text_w)/2:y={y}:font='{caption_font}'"
        )

    ok, err = run([
        FFMPEG, "-y", "-i", video_in,
        "-vf", ",".join(filter_parts),
        "-c:v", "libx264", "-c:a", "copy",
        "-pix_fmt", "yuv420p", "-preset", "fast",
        video_out
    ])
    if not ok:
        print(f"❌ Caption error: {err}")
    return ok


def mix_music(video_in, audio_in, video_out, vol=0.35):
    """Mix music under existing video audio track. Gracefully handles missing audio."""
    ok, err = run([
        FFMPEG, "-y",
        "-i", video_in,
        "-i", audio_in,
        "-filter_complex",
        "[1:a]volume=" + str(vol) + "[a2];[0:a][a2]amix=inputs=2:duration=first[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac",
        "-ar", TARGET_AR, "-ac", TARGET_AC,
        "-shortest",
        video_out
    ])
    if not ok:
        # Fallback: if mixing fails (no audio on video), just use music as audio
        ok2, err2 = run([
            FFMPEG, "-y",
            "-i", video_in,
            "-i", audio_in,
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy", "-c:a", "aac",
            "-ar", TARGET_AR, "-ac", TARGET_AC,
            "-shortest",
            video_out
        ])
        if not ok2:
            print(f"❌ Music mix error: {err2}")
            return False
    return True


def create_outro(logo_path, voice_path, video_out):
    """
    Logo on black, exactly as long as the voiceover.
    Voice is pre-normalized so no format surprises.
    """
    voice_dur = get_duration(voice_path)
    if voice_dur is None:
        print("⚠️  Could not read voiceover duration, defaulting to 3s")
        voice_dur = 3.0
    print(f"         → Voiceover: {voice_dur:.2f}s")

    tmp_logo = video_out.replace(".mp4", "_logo_only.mp4")

    ok, err = run([
        FFMPEG, "-y",
        "-loop", "1", "-i", logo_path,
        "-f", "lavfi", "-i",
        f"color=black:size={TARGET_W}x{TARGET_H}:rate={TARGET_FPS}",
        "-filter_complex",
        "[1:v][0:v]overlay=(W-w)/2:(H-h)/2:shortest=1[v]",
        "-map", "[v]",
        "-t", str(voice_dur),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "fast",
        tmp_logo
    ])
    if not ok:
        print(f"❌ Logo frame error: {err}")
        return False

    ok, err = run([
        FFMPEG, "-y",
        "-i", tmp_logo, "-i", voice_path,
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "aac",
        "-ar", TARGET_AR, "-ac", TARGET_AC,
        "-shortest", video_out
    ])
    if os.path.exists(tmp_logo):
        os.remove(tmp_logo)
    if not ok:
        print(f"❌ Outro audio attach error: {err}")
    return ok


def concat_segments(segments, video_out):
    """
    Concat pre-normalized segments. All streams are identical
    spec so this should be clean and fast every time.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                     delete=False, encoding="utf-8") as f:
        for s in segments:
            f.write(f"file '{s}'\n")
        list_path = f.name

    ok, err = run([
        FFMPEG, "-y",
        "-f", "concat", "-safe", "0", "-i", list_path,
        "-c:v", "libx264", "-c:a", "aac",
        "-ar", TARGET_AR, "-ac", TARGET_AC,
        "-pix_fmt", "yuv420p",
        video_out
    ])
    os.unlink(list_path)
    if not ok:
        print(f"❌ Concat error: {err}")
    return ok


def render_random(index, config, subtitler):
    settings   = config.get("settings", {})
    captions   = config.get("captions", {})
    output_dir = BASE_DIR / settings.get("output_dir", "output")
    output_dir.mkdir(exist_ok=True)
    tmp = output_dir / "_tmp"
    tmp.mkdir(exist_ok=True)

    def pick_long_enough(choices, min_duration, label):
        for _ in range(20):
            pick = resolve(random.choice(choices))
            dur = get_duration(pick)
            if dur is None or dur >= min_duration:
                return pick
        # Fallback: return last pick even if too short
        return resolve(random.choice(choices))

    am_a  = pick_long_enough(config["act_a_music"], CLIP_DURATION, "Act A music")
    am_b  = pick_long_enough(config["act_b_music"], CLIP_DURATION, "Act B music")
    voice = resolve(random.choice(config["voiceover_clips"]))
    logo  = resolve(config.get("logo", ""))

    cap_a     = captions.get("act_a", "When I'm not listening to DJ FLOOD")
    cap_b     = captions.get("act_b", "When I'm listening to DJ FLOOD")
    cap_font  = config.get("caption_font", "Impact")
    music_vol = settings.get("music_volume", 0.35)

    print(f"🎬 Render #{index:03d}")
    print(f"   Music A   → {Path(am_a).name}")
    print(f"   Music B   → {Path(am_b).name}")
    print(f"   Voiceover → {Path(voice).name}")

    t  = lambda n: str(tmp / f"{index:03d}_{n}.mp4")
    ta = lambda n: str(tmp / f"{index:03d}_{n}.aac")

    # ── Normalize everything to identical spec ──
    print(f"   [1/9] Normalize Act A video...")
    max_retries = 5
    for attempt in range(max_retries):
        av_a = pick_long_enough(config["act_a_videos"], CLIP_DURATION, "Act A")
        print(f"         → {Path(av_a).name}")
        ok, sa = normalize_video(av_a, t("a_norm"), CLIP_DURATION, mute=False)
        if ok:
            break
        if attempt < max_retries - 1:
            print(f"         → Retrying with different clip ({attempt + 1}/{max_retries})...")
    if not ok:
        print(f"         → All retries failed, skipping render")
        return False
    print(f"         → @ {sa:.1f}s")

    print(f"   [2/9] Normalize Act B video (muted)...")
    max_retries = 5
    for attempt in range(max_retries):
        av_b = pick_long_enough(config["act_b_videos"], CLIP_DURATION, "Act B")
        print(f"         → {Path(av_b).name}")
        ok, sb = normalize_video(av_b, t("b_norm"), CLIP_DURATION, mute=True)
        if ok:
            break
        if attempt < max_retries - 1:
            print(f"         → Retrying with different clip ({attempt + 1}/{max_retries})...")
    if not ok:
        print(f"         → All retries failed, skipping render")
        return False
    print(f"         → @ {sb:.1f}s")

    # Name the output after the clips that were actually used
    out_name  = f"flood_{index:03d}__{Path(av_a).stem[:18]}__{Path(av_b).stem[:18]}.mp4"
    final_out = str(output_dir / out_name)

    print(f"   [3/9] Normalize Act A music...")
    ok, sma = normalize_audio(am_a, CLIP_DURATION, ta("music_a"))
    if not ok: return False
    print(f"         → @ {sma:.1f}s")

    print(f"   [4/9] Normalize Act B music...")
    ok, smb = normalize_audio(am_b, CLIP_DURATION, ta("music_b"))
    if not ok: return False
    print(f"         → @ {smb:.1f}s")

    print(f"   [5/9] Normalize voiceover...")
    if not normalize_voice(voice, ta("voice")): return False

    # ── Captions ────────────────────────────────

    print(f"   [6/9] Act A caption...")
    if not add_caption(t("a_norm"), cap_a, t("a_cap"), cap_font): return False

    print(f"   [7/9] Act B caption...")
    if not add_caption(t("b_norm"), cap_b, t("b_cap"), cap_font): return False

    # ── Music mix ───────────────────────────────

    print(f"   [8/9] Music mix A + B...")
    if not mix_music(t("a_cap"), ta("music_a"), t("a_final"), music_vol): return False
    if not mix_music(t("b_cap"), ta("music_b"), t("b_final"), music_vol): return False

    # ── Outro ───────────────────────────────────

    print(f"   [9/9] Outro (logo + voiceover)...")
    if not create_outro(logo, ta("voice"), t("outro")): return False

    # ── Final assembly ──────────────────────────

    print(f"   [final] Assembling...")
    if not concat_segments([t("a_final"), t("b_final"), t("outro")], final_out):
        return False

    # ── Subtitles: Act A's own audio and the voiceover (Act B is muted) ──
    if subtitler.enabled:
        print(f"   [subs] Transcribing speech...")
        outro_at = (get_duration(t("a_final")) or CLIP_DURATION) + (get_duration(t("b_final")) or CLIP_DURATION)
        words = subtitler.words(t("a_norm"), 0.0) + subtitler.words(ta("voice"), outro_at)
        subtitler.apply(final_out, words, index)

    for f in tmp.glob(f"{index:03d}_*"):
        f.unlink()

    print(f"   ✅ Done → {out_name}\n")
    return True

# ─────────────────────────────────────────────
#  Automatic subtitles
# ─────────────────────────────────────────────

class Subtitler:
    """
    Burns subtitles into finished renders using subtitles.py. Any problem
    (faster-whisper not installed, a failed transcription) is reported and the
    render is kept without subtitles rather than failing.
    """

    def __init__(self, config):
        import subtitles as st   # imported here: subtitles.py imports this module
        self.st = st
        settings = config.get("settings", {})
        self.enabled = settings.get("auto_subtitles", True)
        self.style = st.SUBTITLE_STYLES.get(settings.get("subtitle_style"), "pop")
        self.model = st.SUBTITLE_MODELS.get(settings.get("subtitle_model"), "small")
        self.font = config.get("caption_font", "Impact")
        self._sources = {}

    def _transcribe(self, path, **kw):
        try:
            return self.st.transcribe(path, model=self.model, **kw)["words"]
        except self.st.SubtitlesUnavailable:
            print(f"   ⚠️  Subtitles turned off for this batch: faster-whisper is not installed.")
            print(f"      {self.st.INSTALL_HINT}")
            self.enabled = False
        except Exception as e:
            print(f"   ⚠️  Could not transcribe {Path(path).name}: {e}")
        return []

    def words(self, path, offset):
        """Words spoken in a short render segment, shifted to where it sits in the final clip."""
        return self.st.shift_words(self._transcribe(path, use_cache=False, quiet=True), offset)

    def source_words(self, path):
        """Full (cached) transcript of a longform source, loaded once per batch."""
        if path not in self._sources:
            self._sources[path] = self._transcribe(path)
        return self._sources[path]

    def apply(self, video, words, index):
        if not self.enabled:
            return
        if not words:
            print(f"         → No speech found, no subtitles for this clip")
            return
        size = (TARGET_W, TARGET_H)
        ass = self.st.write_ass(words, self.style, size, self.font, f"render_{index:03d}")
        tmp_out = video.replace(".mp4", "_subs_tmp.mp4")
        try:
            self.st.burn(video, ass, tmp_out, size)
            os.replace(tmp_out, video)
            Path(video).with_suffix(".srt").write_text(self.st.build_srt(words), encoding="utf-8")
            print(f"         → {len(words)} words subtitled ({self.style})")
        except RuntimeError as e:
            print(f"   ⚠️  Subtitles failed, keeping the clip without them: {e}")
        finally:
            ass.unlink(missing_ok=True)
            if os.path.exists(tmp_out):
                os.remove(tmp_out)


# ─────────────────────────────────────────────
#  Longform clips
# ─────────────────────────────────────────────

def fit_filter():
    """Fill the target frame: the source centered over a blurred, zoomed copy of itself."""
    W, H = TARGET_W, TARGET_H
    return (f"[0:v]split=2[bgsrc][fgsrc];"
            f"[bgsrc]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
            f"boxblur=20:2,eq=brightness=-0.08[bg];"
            f"[fgsrc]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2,fps={TARGET_FPS},format=yuv420p[v]")


def waveform_filter():
    W, H = TARGET_W, TARGET_H
    return (f"color=c=0x1A1A1A:s={W}x{H}:r={TARGET_FPS}[bg];"
            f"[0:a]showwaves=s={W}x{max(H // 4, 16)}:mode=cline:rate={TARGET_FPS}:colors=0xFF4444[wave];"
            f"[bg][wave]overlay=0:(H-h)/2:shortest=1,format=yuv420p[v]")


def cut_excerpt(src, start, length, has_video, out):
    ok, err = run([
        FFMPEG, "-y",
        "-ss", f"{start:.3f}", "-i", src, "-t", f"{length:.3f}",
        "-filter_complex", fit_filter() if has_video else waveform_filter(),
        "-map", "[v]", "-map", "0:a:0?",
        "-c:v", "libx264", "-preset", "fast", "-crf", "21", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ar", TARGET_AR, "-ac", TARGET_AC,
        "-shortest", out
    ])
    if not ok:
        print(f"❌ Excerpt error: {err[-800:]}")
    return ok


def render_longform(index, config, subtitler):
    import subtitles as st
    settings   = config.get("settings", {})
    output_dir = BASE_DIR / settings.get("output_dir", "output")
    tmp = output_dir / "_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    t  = lambda n: str(tmp / f"{index:03d}_{n}.mp4")
    ta = lambda n: str(tmp / f"{index:03d}_{n}.aac")

    src = resolve(random.choice(config["longform_source"]))
    try:
        duration, size = st.probe(src)
    except RuntimeError as e:
        print(f"❌ {e}")
        return False
    length = settings.get("clip_length", 30)
    print(f"🎬 Longform #{index:03d} — {Path(src).name}")

    # Choose the excerpt: sentence-aligned when a transcript is available
    words = subtitler.source_words(src) if subtitler.enabled else []
    start, end = st.pick_excerpt(words, duration, length, random)
    print(f"   [1/3] Excerpt {start:.1f}s → {end:.1f}s ({end - start:.1f}s)"
          + (" · video" if size else " · audio → waveform"))
    if not cut_excerpt(src, start, end - start, size is not None, t("main")):
        return False
    clip_words = st.words_between(words, start, end)
    segments = [t("main")]

    # Optional outro: logo + voiceover, when both are available
    logo = resolve(config["logo"]) if config.get("logo") else None
    voices = config.get("voiceover_clips", [])
    voice_words = []
    if logo and voices:
        print(f"   [2/3] Outro (logo + voiceover)...")
        voice = resolve(random.choice(voices))
        if normalize_voice(voice, ta("voice")) and create_outro(logo, ta("voice"), t("outro")):
            segments.append(t("outro"))
            if subtitler.enabled:
                voice_words = subtitler.words(ta("voice"), get_duration(t("main")) or (end - start))
    else:
        print(f"   [2/3] Outro skipped (needs a logo and a voiceover clip)")

    out_name  = f"longform_{index:03d}__{Path(src).stem[:24]}__{int(start // 60):02d}m{int(start % 60):02d}s.mp4"
    final_out = str(output_dir / out_name)
    print(f"   [3/3] Assembling...")
    if len(segments) > 1:
        if not concat_segments(segments, final_out):
            return False
    else:
        os.replace(t("main"), final_out)

    if subtitler.enabled:
        print(f"   [subs] Adding subtitles...")
        subtitler.apply(final_out, clip_words + voice_words, index)

    for f in tmp.glob(f"{index:03d}_*"):
        f.unlink()
    print(f"   ✅ Done → {out_name}\n")
    return True


def validate_video(path):
    """Quick check if FFmpeg can parse the video. Only scans first 3 seconds."""
    cmd = [
        FFMPEG, "-v", "quiet",     # suppress all output
        "-t", "3",
        "-i", path,
        "-f", "null", "-"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False

def apply_config_targets():
    cfg = load_config()
    settings = cfg.get("settings", {})
    import sys
    # Override module-level constants
    mod = sys.modules[__name__]
    mod.TARGET_W = settings.get("target_w", 1920)
    mod.TARGET_H = settings.get("target_h", 1080)
    mod.TARGET_FPS = settings.get("target_fps", 30)

def main():
    apply_config_targets()
    print("\n══════════════════════════════════════")
    print("   REMIXER v5.2 — RANDOMIZED MODE")
    print("══════════════════════════════════════\n")

    config = load_config()
    longform = config.get("settings", {}).get("template") == "LONGFORM CLIPS"
    check_assets(config, longform)
    global CLIP_DURATION
    CLIP_DURATION = config.get("settings", {}).get("clip_length", 15) / 2
    subtitler = Subtitler(config)

    num_renders = config.get("num_renders", 10)
    print(f"🧩 Template    : {'LONGFORM CLIPS' if longform else 'SAD CLIP / HAPPY CLIP'}")
    print(f"🎯 Output      : {TARGET_W}x{TARGET_H} @ {TARGET_FPS}fps")
    print(f"🎲 Renders     : {num_renders}")
    if longform:
        print(f"✂️  Clip length  : up to {CLIP_DURATION * 2:g}s, cut on sentence boundaries")
    else:
        print(f"✂️  Clip length  : {CLIP_DURATION}s per act")
        print(f"🎵 Audio       : random subsections, all normalized")
    print(f"🎙️  Outro        : matches voiceover duration exactly")
    print(f"💬 Subtitles   : " + (f"on ({subtitler.style}, model {subtitler.model})" if subtitler.enabled else "off") + "\n")

    render = render_longform if longform else render_random
    success = sum(
        bool(render(i, config, subtitler))
        for i in range(1, num_renders + 1)
    )

    print("══════════════════════════════════════")
    print(f"✅ {success}/{num_renders} renders complete")
    print(f"📁 {BASE_DIR / config['settings'].get('output_dir', 'output')}")
    print("══════════════════════════════════════\n")


if __name__ == "__main__":
    main()
