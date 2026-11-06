#!/usr/bin/env python3
"""Bridge between the capcut MCP and CapCut desktop 9.x on macOS.

CapCut reads draft_info.json (root and Timelines/<main>/) and encrypts it once a
project has content, while the MCP reads and writes draft_content.json. So:

  prep <draft> <seed-media.mp4> <seed-audio.m4a>   empty plaintext draft -> draft_content.json with 9:16 canvas and seed segments
  lines <draft> <lines.txt>                         put each narration line on the timeline as text, ready for text to speech
  style <draft> <timeline.json>                     add captions, callouts and push-ins from the plan to draft_content.json
  sync <draft>                                      fix what the MCP leaves wrong, then copy to every file CapCut reads
  check <draft>                                     say whether CapCut has re-encrypted the draft
"""
import json, os, shutil, subprocess, sys, uuid

ROOT = os.path.expanduser("~/Movies/CapCut/User Data/Projects/com.lveditor.draft")
HERE = os.path.dirname(os.path.abspath(__file__))
uid = lambda: str(uuid.uuid4()).upper()


def probe(path, *entries):
    out = subprocess.check_output(["ffprobe", "-v", "error", *entries, "-of", "csv=p=0", path], text=True)
    return out.strip()


def duration_us(path):
    return round(float(probe(path, "-show_entries", "format=duration")) * 1e6)


def has_audio(path):
    return bool(probe(path, "-select_streams", "a", "-show_entries", "stream=index"))


def paths(draft):
    base = os.path.join(ROOT, draft)
    project = json.load(open(os.path.join(base, "Timelines", "project.json")))
    timeline = os.path.join(base, "Timelines", project["main_timeline_id"])
    return base, timeline


def is_plain(path):
    with open(path, "rb") as f:
        return f.read(1) == b"{"


def prep(draft, video, audio):
    base, _ = paths(draft)
    if os.path.exists(os.path.join(base, ".locked")):
        sys.exit("draft is open in CapCut; close the project first")
    info = os.path.join(base, "draft_info.json")
    if not is_plain(info):
        sys.exit("draft_info.json is encrypted; start from a new empty project")
    d = json.load(open(info))
    seed = json.load(open(os.path.join(HERE, "capcut_seed.json")))
    d["canvas_config"] = {"ratio": "original", "width": 1080, "height": 1920, "background": None}
    d["materials"] = {**d["materials"], **seed["materials"]}
    d["tracks"] = seed["tracks"]
    d["materials"]["videos"][0]["path"] = video
    d["materials"]["audios"][0]["path"] = audio
    d["duration"] = 3_000_000
    shutil.copy(info, info + ".pre-mcp")
    json.dump(d, open(os.path.join(base, "draft_content.json"), "w"))
    print("prepared", draft)


def sync(draft):
    base, timeline = paths(draft)
    if os.path.exists(os.path.join(base, ".locked")):
        sys.exit("draft is open in CapCut; close the project first")
    src = os.path.join(base, "draft_content.json")
    d = json.load(open(src))
    used = {s["material_id"] for t in d["tracks"] for s in t["segments"]}
    refs = {r for t in d["tracks"] for s in t["segments"] for r in s.get("extra_material_refs", [])}
    keep = used | refs
    for key, items in d["materials"].items():
        if isinstance(items, list) and items and isinstance(items[0], dict) and "id" in items[0]:
            d["materials"][key] = [m for m in items if m["id"] in keep]
    for m in d["materials"].get("videos", []):
        m["duration"] = duration_us(m["path"]) if m["type"] == "video" else 10_800_000_000
        m["has_audio"] = m["type"] == "video" and has_audio(m["path"])
    for m in d["materials"].get("audios", []):
        m["duration"] = duration_us(m["path"])
        m["name"] = os.path.basename(m["path"])
        m["type"] = "extract_music"
    d["duration"] = max((s["target_timerange"]["start"] + s["target_timerange"]["duration"]
                         for t in d["tracks"] for s in t["segments"]), default=0)
    text = json.dumps(d)
    with open(src, "w") as f:
        f.write(text)
    for dst in (os.path.join(base, n) for n in ("draft_info.json", "draft_info.json.bak", "template-2.tmp")):
        with open(dst, "w") as f:
            f.write(text)
    for n in ("draft_info.json", "draft_info.json.bak", "template-2.tmp"):
        with open(os.path.join(timeline, n), "w") as f:
            f.write(text)
    print("synced", draft, "duration", d["duration"] / 1e6)


def lines(draft, path):
    base, _ = paths(draft)
    src = os.path.join(base, "draft_content.json")
    d = json.load(open(src))
    track = next(t for t in d["tracks"] if t["type"] == "text")
    seed = track["segments"][0]
    seed_mat = next(m for m in d["materials"]["texts"] if m["id"] == seed["material_id"])
    track["segments"], d["materials"]["texts"] = [], []
    for i, line in enumerate(l.strip() for l in open(path) if l.strip()):
        mat = json.loads(json.dumps(seed_mat))
        mat["id"] = uid()
        content = json.loads(mat["content"])
        content["text"] = line
        content["styles"][0]["range"] = [0, len(line)]
        mat["content"] = json.dumps(content, ensure_ascii=False)
        seg = json.loads(json.dumps(seed))
        seg["id"] = uid()
        seg["material_id"] = mat["id"]
        seg["extra_material_refs"] = []
        seg["target_timerange"] = {"start": i * 6_000_000, "duration": 6_000_000}
        seg["render_index"] = 15000 + i
        d["materials"]["texts"].append(mat)
        track["segments"].append(seg)
    next(t for t in d["tracks"] if t["type"] == "audio")["segments"] = []
    json.dump(d, open(src, "w"))
    print("lines added:", len(track["segments"]))


def chunks(text, limit=24):
    """Split a sentence into short caption phrases without breaking words."""
    out, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > limit:
            out.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return out + [cur] if cur else out


def style(draft, plan_path):
    base, _ = paths(draft)
    src = os.path.join(base, "draft_content.json")
    d = json.load(open(src))
    plan = json.load(open(plan_path))
    track = next(t for t in d["tracks"] if t["type"] == "text")
    seed = track["segments"][0]
    seed_mat = next(m for m in d["materials"]["texts"] if m["id"] == seed["material_id"])
    track["segments"] = []
    d["materials"]["texts"] = []
    render = [15000]

    def add(text, start, end, y, size, color=(1, 1, 1), stroke=0.07):
        mat = json.loads(json.dumps(seed_mat))
        mat["id"] = uid()
        mat["check_flag"] = 7 | 8 | 32
        mat["content"] = json.dumps({"text": text, "styles": [{
            "fill": {"alpha": 1.0, "content": {"render_type": "solid", "solid": {"alpha": 1.0, "color": list(color)}}},
            "range": [0, len(text)], "size": size, "bold": True, "italic": False, "underline": False,
            "strokes": [{"content": {"solid": {"alpha": 1.0, "color": [0, 0, 0]}}, "width": stroke}],
            "shadows": [{"diffuse": 0.03, "alpha": 0.7, "distance": 5.0, "content": {"solid": {"color": [0, 0, 0]}}, "angle": -45.0}],
        }]}, ensure_ascii=False)
        seg = json.loads(json.dumps(seed))
        seg["id"] = uid()
        seg["material_id"] = mat["id"]
        seg["extra_material_refs"] = []
        seg["clip"]["transform"]["y"] = y
        seg["target_timerange"] = {"start": round(start * 1e6), "duration": round((end - start) * 1e6)}
        seg["render_index"] = render[0]
        render[0] += 1
        d["materials"]["texts"].append(mat)
        track["segments"].append(seg)

    for cap in plan["captions"]:
        parts = chunks(cap["text"])
        begin, span = cap["at"] + cap["from"], cap["to"] - cap["from"]
        total = sum(len(p) + 2 for p in parts)
        for part in parts:
            step = span * (len(part) + 2) / total
            add(part, begin, begin + step, -0.60, 15)
            begin += step
    yellow = (1.0, 0.82, 0.1)
    for call in plan["callouts"]:
        add(call["text"], call["start"], call["end"], 0.70, call["size"], yellow, 0.05)
        if call.get("sub"):
            add(call["sub"], call["start"], call["end"], 0.56, 11, (1, 1, 1), 0.06)
    credit = plan["credit"]
    add(credit["text"], credit["start"], credit["end"], -0.80, 7, (0.92, 0.92, 0.92), 0.05)

    video = next(t for t in d["tracks"] if t["type"] == "video")
    video["segments"].sort(key=lambda s: s["target_timerange"]["start"])
    for seg, scene in zip(video["segments"], plan["scenes"]):
        dur = seg["target_timerange"]["duration"]

        def curve(prop, a, b):
            return {"id": uid(), "material_id": "", "property_type": prop, "keyframe_list": [
                {"id": uid(), "curveType": "Line", "graphID": "", "left_control": {"x": 0.0, "y": 0.0},
                 "right_control": {"x": 0.0, "y": 0.0}, "time_offset": t, "values": [v]}
                for t, v in ((0, a), (dur, b))]}

        a, b = scene.get("push", [1.0, 1.0])
        seg["common_keyframes"] = [curve("UNIFORM_SCALE", a, b)] if a != b else []
        if scene.get("rise"):
            seg["common_keyframes"].append(curve("KFTypePositionY", 0.0, scene["rise"]))
    with open(src, "w") as f:
        json.dump(d, f)
    print("styled", draft, len(track["segments"]), "text segments")


def check(draft):
    base, _ = paths(draft)
    print("plain" if is_plain(os.path.join(base, "draft_info.json")) else "encrypted")


if __name__ == "__main__":
    {"prep": prep, "lines": lines, "style": style, "sync": sync, "check": check}[sys.argv[1]](*sys.argv[2:])
