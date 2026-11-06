#!/usr/bin/env python3
"""Retime each finished scene master to its narration slot, and make the black card clip.

  fit_scenes.py <post-dir> [scene-file ...]   reads timeline.json, writes assets/fit/

  speed: play the whole clip faster or slower to fill the slot (for action shots)
  hold:  play at real speed, then hold the last frame
  slow:  slow the action by "slow" with blended frames, then hold the last frame
"""
import json, os, subprocess, sys

post = sys.argv[1]
only = set(sys.argv[2:])
plan = json.load(open(os.path.join(post, "timeline.json")))
out_dir = os.path.join(post, "assets", "fit")
os.makedirs(out_dir, exist_ok=True)
BLEND = "framerate=fps=30:interp_start=32:interp_end=224"


def length(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], text=True))


black = os.path.join(out_dir, "black-card.mp4")
if not only:
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=1080x1920:r=30:d=4",
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", black], check=True)

for scene in plan["scenes"]:
    if scene.get("card") or scene.get("photo") or (only and scene["file"] not in only):
        continue
    src = os.path.join(post, "assets", scene["file"])
    src_len = length(src)
    slot = scene["end"] - scene["start"]
    if scene["fit"] == "speed":
        chain = f"setpts=PTS*{slot / src_len:.6f},{BLEND}"
    else:
        factor = 1 / scene["slow"] if scene["fit"] == "slow" else 1.0
        extra = max(0.0, slot - src_len * factor)
        chain = f"setpts=PTS*{factor:.6f},{BLEND},tpad=stop_mode=clone:stop_duration={extra:.3f}"
    dst = os.path.join(out_dir, scene["file"])
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-vf", chain, "-t", f"{slot:.3f}", "-r", "30",
                    "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p", "-an", dst], check=True)
    print(f"{scene['file']}: slot {slot:.2f}s, got {length(dst):.2f}s ({scene['fit']})")
