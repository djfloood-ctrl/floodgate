import subprocess, datetime

log = subprocess.run(["git", "log", "--pretty=format:%H|%ai|%s"], capture_output=True, text=True)

commits_html = ""
for line in log.stdout.strip().split("\n"):
    if not line: continue
    parts = line.split("|")
    if len(parts) >= 3:
        commit_hash = parts[0][:7]
        date = parts[1][:10]
        msg = "|".join(parts[2:])
        commits_html += f"                <tr><td>{date}</td><td><code>{commit_hash}</code></td><td>{msg}</td></tr>\n"

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FLOODGATE — Whitepaper</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ background: #8B1A1A; color: #F0E8E0; font-family: 'Helvetica Neue', 'Segoe UI', sans-serif; line-height: 1.7; }}
        .container {{ max-width: 960px; margin: 0 auto; padding: 60px 40px; }}
        .logo {{ font-size: 48px; font-weight: 900; letter-spacing: -2px; margin-bottom: 4px; }}
        .tagline {{ font-family: 'Courier New', monospace; color: #C8B0B0; font-size: 11px; text-transform: uppercase; letter-spacing: 4px; margin-bottom: 40px; }}
        .divider {{ height: 1px; background: #C84040; margin: 50px 0; }}
        h1 {{ font-size: 36px; font-weight: 900; margin-bottom: 20px; }}
        h2 {{ font-size: 22px; font-weight: 700; margin: 40px 0 16px; color: #FF4444; }}
        h3 {{ font-size: 16px; font-weight: 700; margin: 24px 0 10px; }}
        p {{ margin-bottom: 16px; color: #E8DDD4; }}
        ul {{ margin: 12px 0 20px 20px; }}
        li {{ margin-bottom: 8px; color: #E8DDD4; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 13px; }}
        th {{ background: #6B1010; padding: 12px 16px; text-align: left; font-family: 'Courier New', monospace; color: #FF4444; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }}
        td {{ padding: 10px 16px; border-bottom: 1px solid #9E2020; font-family: 'Courier New', monospace; font-size: 12px; }}
        tr:hover td {{ background: #9E2020; }}
        code {{ background: #6B1010; padding: 2px 6px; border-radius: 4px; font-size: 12px; }}
        .footer {{ margin-top: 60px; color: #C8B0B0; font-family: 'Courier New', monospace; font-size: 11px; text-align: center; }}
        @media (max-width: 768px) {{ .container {{ padding: 30px 20px; }} .logo {{ font-size: 32px; }} }}
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">FLOODGATE</div>
        <div class="tagline">Short-Form Content Engine • Whitepaper v2.3</div>

        <div class="divider"></div>

        <h1>What Is FLOODGATE?</h1>
        <p>FLOODGATE is a short-form content generation engine that transforms raw video, audio, and voiceover assets into randomized, formatted, captioned clips optimized for Instagram Reels, TikTok, YouTube Shorts, and more. It is built on FFmpeg and addresses a practical problem for creators and marketing teams: short-form platforms reward frequent posting, and editing each clip by hand does not scale.</p>
        <p>FLOODGATE turns one library of source material into a large batch of distinct clips. Each render draws different source clips, timestamps, music excerpts and voiceovers, and runs unattended once started.</p>

        <h2>Core Capabilities</h2>
        <ul>
            <li><strong>Contrast Engine</strong> — Sad vs. Happy clip pairing with music beds and AI voiceovers</li>
            <li><strong>Format Presets</strong> — Instagram Reel (1080×1920), TikTok, YouTube Shorts, Widescreen (16:9), Cinematic (21:9)</li>
            <li><strong>Asset Management</strong> — Drag-and-drop video, audio, and voiceover slots with file size tracking</li>
            <li><strong>Smart Browse</strong> — Gallery view with favorites, tags, folders, search, and sort-by-date/views/name</li>
            <li><strong>Trash System</strong> — Instant trash with restore, permanent delete with confirmation</li>
            <li><strong>Live Remixer Log</strong> — Render output streams into the app; the gallery refreshes when the batch completes</li>
            <li><strong>Project Bins</strong> — Save/load artist profiles with independent asset pools and settings</li>
                    </ul>

        <h2>Business Applications</h2>
        <h3>Music Industry</h3>
        <p>Artists and DJs can generate hundreds of promotional clips from a single music video, live set recording, or studio session. Each clip features different sections of the track, different visual moments, and branded captions — ready for Reels, TikTok, and Stories.</p>
        <h3>Content Agencies</h3>
        <p>Scale short-form production from dozens to thousands of clips per client per month. Template-based rendering ensures brand consistency across all output. The browse and tag system enables rapid content library management.</p>
        <h3>Podcast Networks</h3>
        <p>Once longform rendering is available, extract highlight clips from full episodes and pair them with branded visuals and captions.</p>
        <h3>Sports Media</h3>
        <p>Clip goal reactions, highlight plays, and post-game moments in batches. Multiple format outputs from a single source file.</p>
        <h3>Comedy & Entertainment</h3>
        <p>Turn specials and sets into hundreds of shareable clips. Random timestamp selection gives each clip different material.</p>

        <div class="divider"></div>

        <h2>Commit History</h2>
        <table>
            <thead>
                <tr><th>Date</th><th>Commit</th><th>Description</th></tr>
            </thead>
            <tbody>
{commits_html}
            </tbody>
        </table>

        <div class="divider"></div>

        <p class="footer">FLOODGATE v2.3 — Python, CustomTkinter and FFmpeg.</p>
    </div>
</body>
</html>
"""

with open("FLOODGATE_Whitepaper.html", "w", encoding="utf-8") as f:
    f.write(html)

print("FLOODGATE_Whitepaper.html created - open in browser")