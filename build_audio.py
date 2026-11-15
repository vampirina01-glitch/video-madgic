"""Mix VO clips (at timeline offsets) with the synthesized music into mix.wav."""
import json, subprocess, sys
import imageio_ffmpeg
from timeline import TIMELINE

FF = imageio_ffmpeg.get_ffmpeg_exe()
TOTAL = TIMELINE["total"]

scenes = TIMELINE["scenes"]
cmd = [FF, "-y"]
for s in scenes:
    cmd += ["-i", s["vo"]]
cmd += ["-i", "assets/audio/music.wav"]

parts = []
for i, s in enumerate(scenes):
    ms = int(s["vo_start"] * 1000)
    parts.append(f"[{i}:a]adelay={ms}|{ms},volume=1.65[a{i}]")
music_idx = len(scenes)
parts.append(f"[{music_idx}:a]volume=0.34[mus]")
mix_inputs = "".join(f"[a{i}]" for i in range(len(scenes)))
parts.append(f"{mix_inputs}amix=inputs={len(scenes)}:normalize=0:duration=longest[vo]")
parts.append("[vo][mus]amix=inputs=2:normalize=0:duration=longest[mix]")
parts.append("[mix]alimiter=limit=0.95,apad=whole_dur=%.3f[out]" % TOTAL)
filter_complex = ";".join(parts)

cmd += ["-filter_complex", filter_complex, "-map", "[out]",
        "-t", str(TOTAL), "-ar", "48000", "-ac", "2", "assets/audio/mix.wav"]
print("running ffmpeg mix…")
subprocess.run(cmd, check=True)
print("mix written: assets/audio/mix.wav  total", TOTAL, "s")
