#!/usr/bin/env python3
"""Build a card-driven cut on top of a draft the person has worked on in CapCut.

Keeps their narration, captions and styles. Never run on a draft that's open in CapCut.

  cut.py open <draft> <timeline.json>    copy CapCut's file for the MCP, move narration and captions to their slots, fix captions.
                                         Safe while the project is open: CapCut 9.x doesn't read draft_content.json.
  (then capcut_add_video each scene through the MCP, delete the old video, capcut_save with force:true if it's open)
  cut.py finish <draft> <timeline.json>  add title cards, the sting on each card, push-ins; write every file CapCut reads.
                                         The project must be closed, and stops if the timeline changed since "open".
  cut.py build <draft> <timeline.json>   one step for a new video: narration already generated in <draft>. Lays out scenes, cards and
                                         captions, and copies the caption style, sting, filter, grain and typing from "donor_draft".
  cut.py polish <draft> <timeline.json>  re-lay the whole cut from the plan: scene slots, real photos, narration, captions,
                                         card size and typing, stings only where marked, filter and grain under the text.
"""
import json, os, shutil, sys, uuid

ROOT = os.path.expanduser("~/Movies/CapCut/User Data/Projects/com.lveditor.draft")
HERE = os.path.dirname(os.path.abspath(__file__))
uid = lambda: str(uuid.uuid4()).upper()
MS = 1000


def load_plan(path):
    return json.load(open(path))


def shift_for(start, plan):
    offset = 0.0
    for at, shift in plan["shifts"]:
        if start >= (at - 0.02) * 1e6:
            offset = shift
    return round(offset * 1e6)


def set_text(mat, words_text, starts, ends):
    text = "".join(words_text)
    content = json.loads(mat["content"])
    content["text"] = text
    for style in content["styles"]:
        style["range"] = [0, len(text)]
    mat["content"] = json.dumps(content, ensure_ascii=False)
    mat["recognize_text"] = text
    mat["words"] = {"start_time": starts, "end_time": ends, "text": words_text}


def fix_captions(d, fixes):
    mats = d["materials"]
    texts = {t["id"]: t for t in mats["texts"]}
    templates = {t["id"]: t for t in mats["text_templates"]}
    anims = {a["id"]: a for a in mats["material_animations"]}
    track = next(t for t in d["tracks"] if t["type"] == "text")
    rows = []
    for seg in track["segments"]:
        res = templates[seg["material_id"]]["text_info_resources"][0]
        rows.append((seg, res, texts[res["text_material_id"]]))

    for _, _, mat in rows:
        w = mat["words"]
        tx, st, en = list(w["text"]), list(w["start_time"]), list(w["end_time"])
        tx = [fixes["replace"].get(t, t) for t in tx]
        for a, b, joined in fixes["merge"]:
            for i in range(len(tx) - 2):
                if tx[i] == a and tx[i + 2] == b:
                    tx[i:i + 3] = [joined]
                    en[i:i + 3] = [en[i + 2]]
                    st[i:i + 3] = [st[i]]
                    break
        set_text(mat, tx, st, en)

    move = fixes.get("move_tail")
    if move:
        def resize(seg, res, new_start, new_dur):
            seg["target_timerange"] = {"start": new_start, "duration": new_dur}
            res["attach_info"]["duration"] = new_dur
            for ref in seg.get("extra_material_refs", []):
                if ref in anims:
                    for a in anims[ref]["animations"]:
                        a["duration"] = new_dur

        full = lambda m: json.loads(m["content"])["text"]
        src = next(r for r in rows if full(r[2]) == move["from"])
        dst = next(r for r in rows if full(r[2]) == move["into"])
        w = src[2]["words"]
        cut = len(w["text"]) - (move["words"] * 2 - 1)
        tail_tx, tail_st, tail_en = w["text"][cut:], w["start_time"][cut:], w["end_time"][cut:]
        tail_base = tail_st[0]
        tail_len = tail_en[-1] - tail_base
        new_start = src[0]["target_timerange"]["start"] + tail_base * MS
        old_end = dst[0]["target_timerange"]["start"] + dst[0]["target_timerange"]["duration"]
        lead = dst[0]["target_timerange"]["start"] - new_start
        lead_ms = round(lead / MS)
        v = dst[2]["words"]
        set_text(dst[2], tail_tx + [" "] + v["text"],
                 [s - tail_base for s in tail_st] + [lead_ms] + [s + lead_ms for s in v["start_time"]],
                 [e - tail_base for e in tail_en] + [lead_ms] + [e + lead_ms for e in v["end_time"]])
        keep_tx, keep_st, keep_en = w["text"][:cut - 1], w["start_time"][:cut - 1], w["end_time"][:cut - 1]
        set_text(src[2], keep_tx, keep_st, keep_en)
        resize(src[0], src[1], src[0]["target_timerange"]["start"], keep_en[-1] * MS)
        resize(dst[0], dst[1], new_start, old_end - new_start)
        print("moved", tail_tx, "lead ms", lead_ms, "tail", tail_len)


def open_draft(draft, plan_path):
    base = os.path.join(ROOT, draft)
    info = os.path.join(base, "draft_info.json")
    if open(info, "rb").read(1) != b"{":
        sys.exit("draft_info.json is encrypted")
    shutil.copy(info, info + ".before-cut")
    d = json.load(open(info))
    plan = load_plan(plan_path)
    fix_captions(d, plan["caption_fixes"])
    for seg in next(t for t in d["tracks"] if t["type"] == "text")["segments"]:
        seg["target_timerange"]["start"] += shift_for(seg["target_timerange"]["start"], plan)
    # Narration goes by line order, so edits made in the app can't throw it off.
    kinds = {a["id"]: a["type"] for a in d["materials"]["audios"]}
    lines = sorted((s for t in d["tracks"] if t["type"] == "audio" for s in t["segments"]
                    if kinds[s["material_id"]] == "text_to_audio"), key=lambda s: s["target_timerange"]["start"])
    if len(lines) != len(plan["narration_at"]):
        sys.exit(f"expected {len(plan['narration_at'])} narration lines, found {len(lines)}")
    for seg, at in zip(lines, plan["narration_at"]):
        seg["target_timerange"]["start"] = round(at * 1e6)
    json.dump(d, open(os.path.join(base, "draft_content.json"), "w"))
    print("ready for the MCP:", draft)


def card_track(d, plan):
    seed = json.load(open(os.path.join(HERE, "capcut_seed.json")))
    seed_track = next(t for t in seed["tracks"] if t["type"] == "text")
    seg0 = seed_track["segments"][0]
    mat0 = seed["materials"]["texts"][0]
    track = dict(seed_track, id=uid(), segments=[], name="cards")
    render = 20000
    for card in plan["cards"]:
        mat = json.loads(json.dumps(mat0))
        mat["id"] = uid()
        mat["alignment"] = 1
        mat["line_spacing"] = 0.12
        mat["content"] = json.dumps({"text": card["text"], "styles": [{
            "fill": {"alpha": 1.0, "content": {"render_type": "solid", "solid": {"alpha": 1.0, "color": [0.96, 0.95, 0.9]}}},
            "range": [0, len(card["text"])], "size": 11.0, "bold": False, "italic": False, "underline": False,
            "strokes": [], "font": {"id": "", "path": plan.get("card_font", "/System/Library/Fonts/Supplemental/Optima.ttc")},
        }]}, ensure_ascii=False)
        seg = json.loads(json.dumps(seg0))
        seg["id"] = uid()
        seg["material_id"] = mat["id"]
        seg["extra_material_refs"] = []
        seg["target_timerange"] = {"start": round(card["start"] * 1e6), "duration": round((card["end"] - card["start"]) * 1e6)}
        seg["source_timerange"] = None
        seg["render_index"] = render
        render += 1
        seg["track_render_index"] = len(d["tracks"])
        d["materials"]["texts"].append(mat)
        track["segments"].append(seg)
    d["tracks"].append(track)


def stings(d, plan):
    track = next(t for t in d["tracks"] if t["type"] == "audio" and any(
        next((a for a in d["materials"]["audios"] if a["id"] == s["material_id"]), {}).get("type") == "extract_music"
        for s in t["segments"]))
    seg = next(s for s in track["segments"] if next(a for a in d["materials"]["audios"] if a["id"] == s["material_id"])["type"] == "extract_music")
    dur = seg["target_timerange"]["duration"]
    track["segments"] = [s for s in track["segments"] if s is not seg]
    for i, card in enumerate(plan["cards"]):
        new = json.loads(json.dumps(seg))
        new["id"] = uid()
        new["target_timerange"] = {"start": round(card["start"] * 1e6), "duration": dur}
        track["segments"].append(new)
    track["segments"].sort(key=lambda s: s["target_timerange"]["start"])


def pushes(d, plan):
    video = next(t for t in d["tracks"] if t["type"] == "video")
    video["segments"].sort(key=lambda s: s["target_timerange"]["start"])
    for seg, scene in zip(video["segments"], plan["scenes"]):
        dur = seg["target_timerange"]["duration"]

        def curve(prop, a, b):
            return {"id": uid(), "material_id": "", "property_type": prop, "keyframe_list": [
                {"id": uid(), "curveType": "Line", "graphID": "", "left_control": {"x": 0.0, "y": 0.0},
                 "right_control": {"x": 0.0, "y": 0.0}, "time_offset": t, "values": [v]}
                for t, v in ((0, a), (dur, b))]}

        frames = []
        if scene.get("push"):
            frames.append(curve("UNIFORM_SCALE", *scene["push"]))
        if scene.get("rise"):
            frames.append(curve("KFTypePositionY", 0.0, scene["rise"]))
        seg["common_keyframes"] = frames


def finish(draft, plan_path):
    base = os.path.join(ROOT, draft)
    if os.path.exists(os.path.join(base, ".locked")):
        sys.exit("draft is open in CapCut; close the project first")
    info = os.path.join(base, "draft_info.json")
    if open(info, "rb").read(1) != b"{":
        sys.exit("draft_info.json is encrypted; stopping")

    def layout(path):
        return [(t["type"], sorted((s["id"], s["target_timerange"]["start"], s["target_timerange"]["duration"]) for s in t["segments"]))
                for t in json.load(open(path))["tracks"]]

    if layout(info) != layout(info + ".before-cut"):
        sys.exit("the timeline changed in CapCut since 'open'; run 'open' again so those edits aren't lost")
    src = os.path.join(base, "draft_content.json")
    d = json.load(open(src))
    plan = load_plan(plan_path)
    card_track(d, plan)
    stings(d, plan)
    pushes(d, plan)
    for m in d["materials"]["videos"]:
        if m.get("type") == "video" and os.path.exists(m.get("path", "")):
            import subprocess
            m["duration"] = round(float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", m["path"]], text=True)) * 1e6)
            m["has_audio"] = False
    d["duration"] = round(plan["total"] * 1e6)
    text = json.dumps(d)
    project = json.load(open(os.path.join(base, "Timelines", "project.json")))
    timeline = os.path.join(base, "Timelines", project["main_timeline_id"])
    for folder in (base, timeline):
        for name in ("draft_info.json", "draft_info.json.bak", "template-2.tmp"):
            with open(os.path.join(folder, name), "w") as f:
                f.write(text)
    with open(src, "w") as f:
        f.write(text)
    print("finished", draft, "segments", [(t["type"], len(t["segments"])) for t in d["tracks"]])


def polish(draft, plan_path):
    import subprocess
    base = os.path.join(ROOT, draft)
    if os.path.exists(os.path.join(base, ".locked")):
        sys.exit("draft is open in CapCut; close the project first")
    info = os.path.join(base, "draft_info.json")
    if open(info, "rb").read(1) != b"{":
        sys.exit("draft_info.json is encrypted; stopping")
    d = json.load(open(info))
    shutil.copy(info, info + ".before-polish")
    plan = load_plan(plan_path)
    post = os.path.dirname(os.path.abspath(plan_path))
    fit = os.path.join(post, "assets", "fit")
    mats = d["materials"]
    us = lambda sec: round(sec * 1e6)

    def probe(path):
        return us(float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], text=True)))

    # Video: reuse each clip by file name, and clone a clip for anything new.
    video = next(t for t in d["tracks"] if t["type"] == "video")
    vid_mat = {m["id"]: m for m in mats["videos"]}
    pool = {}
    for seg in sorted(video["segments"], key=lambda s: s["target_timerange"]["start"]):
        pool.setdefault(os.path.basename(vid_mat[seg["material_id"]]["path"]), []).append(seg)
    template = next(iter(pool.values()))[0]
    built = []
    for scene in plan["scenes"]:
        seg = (pool.get(scene["file"]) or [None]).pop(0) if pool.get(scene["file"]) else None
        path = os.path.join(fit, scene["file"])
        if seg is None:
            seg = json.loads(json.dumps(template))
            seg["id"] = uid()
            mat = json.loads(json.dumps(vid_mat[template["material_id"]]))
            mat["id"] = uid()
            mat["path"] = path
            mat["material_name"] = scene["file"]
            mats["videos"].append(mat)
            vid_mat[mat["id"]] = mat
            seg["material_id"] = mat["id"]
        vid_mat[seg["material_id"]]["duration"] = probe(path)
        dur = us(scene["end"] - scene["start"])
        seg["target_timerange"] = {"start": us(scene["start"]), "duration": dur}
        seg["source_timerange"] = {"start": 0, "duration": min(dur, vid_mat[seg["material_id"]]["duration"])}
        built.append(seg)
    video["segments"] = built
    pushes(d, plan)

    # Narration by line order, captions by their current position.
    tracks = d["tracks"]
    kinds = {a["id"]: a["type"] for a in mats["audios"]}
    audio_tracks = [t for t in tracks if t["type"] == "audio"]
    every = [s for t in audio_tracks for s in t["segments"]]
    lines = sorted((s for s in every if kinds[s["material_id"]] == "text_to_audio"), key=lambda s: s["target_timerange"]["start"])
    stings_all = [s for s in every if kinds[s["material_id"]] == "extract_music"]
    if len(lines) != len(plan["narration_at"]):
        sys.exit(f"expected {len(plan['narration_at'])} narration lines, found {len(lines)}")
    for seg, at in zip(lines, plan["narration_at"]):
        seg["target_timerange"]["start"] = us(at)
    sting_seg = stings_all[0]
    new_stings = []
    for card in plan["cards"]:
        if card.get("sting"):
            new = json.loads(json.dumps(sting_seg))
            new["id"] = uid()
            new["target_timerange"] = {"start": us(card["start"]), "duration": sting_seg["target_timerange"]["duration"]}
            new_stings.append(new)
    audio_tracks[0]["segments"] = sorted(lines + new_stings, key=lambda s: s["target_timerange"]["start"])
    tracks[:] = [t for t in tracks if t["type"] != "audio" or t is audio_tracks[0]]

    templates = {t["id"] for t in mats.get("text_templates", [])}
    text_tracks = [t for t in tracks if t["type"] == "text"]
    captions = next(t for t in text_tracks if t["segments"] and t["segments"][0]["material_id"] in templates)
    for seg in captions["segments"]:
        start = seg["target_timerange"]["start"]
        move = 0.0
        for at, delta in plan["caption_moves"]:
            if start >= us(at - 0.02):
                move = delta
        seg["target_timerange"]["start"] = start + us(move)

    # Cards: bigger text, the same typing animation on each.
    cards = next(t for t in text_tracks if t is not captions)
    anims = mats["material_animations"]
    typer = next(a for a in anims if any(x.get("name") == "Retro Typer" for x in a["animations"]))
    texts = {t["id"]: t for t in mats["texts"]}
    credit = plan.get("photo_credit")
    is_credit = lambda seg: credit and json.loads(texts[seg["material_id"]]["content"])["text"] == credit["text"]
    segs = sorted((s for s in cards["segments"] if not is_credit(s)), key=lambda s: s["target_timerange"]["start"])
    for seg, card in zip(segs, plan["cards"]):
        seg["target_timerange"] = {"start": us(card["start"]), "duration": us(card["end"] - card["start"])}
        mat = texts[seg["material_id"]]
        content = json.loads(mat["content"])
        for style in content["styles"]:
            style["size"] = plan["card_size"]
        mat["content"] = json.dumps(content, ensure_ascii=False)
        anim = json.loads(json.dumps(typer))
        anim["id"] = uid()
        for a in anim["animations"]:
            a["duration"] = us(plan["card_typing"])
        anims.append(anim)
        seg["extra_material_refs"] = [anim["id"]]
    used = {r for t in text_tracks for s in t["segments"] for r in s.get("extra_material_refs", [])}
    anims[:] = [a for a in anims if a["id"] in used]

    # Photo credit, on its own track above the cards' layer.
    if credit and not any(is_credit(s) for s in cards["segments"]):
        seg = json.loads(json.dumps(segs[0]))
        seg["id"] = uid()
        mat = json.loads(json.dumps(texts[seg["material_id"]]))
        mat["id"] = uid()
        content = json.loads(mat["content"])
        content["text"] = credit["text"]
        for style in content["styles"]:
            style["range"] = [0, len(credit["text"])]
            style["size"] = 6.0
        mat["content"] = json.dumps(content, ensure_ascii=False)
        mats["texts"].append(mat)
        seg["material_id"] = mat["id"]
        seg["extra_material_refs"] = []
        seg["target_timerange"] = {"start": us(credit["start"]), "duration": us(credit["end"] - credit["start"])}
        seg["clip"]["transform"]["y"] = -0.86
        seg["render_index"] = 21000
        cards["segments"].append(seg)

    # Filter and grain cover the whole cut, below the text so type stays white.
    for track in tracks:
        if track["type"] in ("filter", "effect"):
            for seg in track["segments"]:
                seg["target_timerange"] = {"start": 0, "duration": us(plan["total"])}
    for m in mats.get("effects", []):
        if m.get("type") == "filter":
            m["value"] = plan["filter_strength"]
    for m in mats.get("video_effects", []):
        for param in m.get("adjust_params") or []:
            if param.get("name") in plan.get("grain_params", {}):
                param["value"] = plan["grain_params"][param["name"]]
    order = {"video": 0, "filter": 1, "effect": 2, "text": 3, "audio": 4}
    tracks.sort(key=lambda t: order.get(t["type"], 5))
    for index, track in enumerate(tracks):
        for seg in track["segments"]:
            seg["track_render_index"] = index
    d["duration"] = us(plan["total"])

    text = json.dumps(d)
    project = json.load(open(os.path.join(base, "Timelines", "project.json")))
    timeline = os.path.join(base, "Timelines", project["main_timeline_id"])
    for folder in (base, timeline):
        for name in ("draft_info.json", "draft_info.json.bak", "template-2.tmp"):
            with open(os.path.join(folder, name), "w") as f:
                f.write(text)
    with open(os.path.join(base, "draft_content.json"), "w") as f:
        f.write(text)
    print("polished", draft, [(t["type"], len(t["segments"])) for t in tracks])


def caption_chunks(text, limit=30):
    out, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > limit:
            out.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return out + [cur] if cur else out


def build(draft, plan_path):
    import subprocess
    base = os.path.join(ROOT, draft)
    if os.path.exists(os.path.join(base, ".locked")):
        sys.exit("draft is open in CapCut; close the project first")
    info = os.path.join(base, "draft_info.json")
    shutil.copy(info, info + ".before-build")
    d = json.load(open(info))
    plan = load_plan(plan_path)
    donor = json.load(open(os.path.join(ROOT, plan["donor_draft"], "draft_info.json")))
    post = os.path.dirname(os.path.abspath(plan_path))
    fit = os.path.join(post, "assets", "fit")
    mats, dm = d["materials"], donor["materials"]
    us = lambda sec: round(sec * 1e6)

    def probe(path):
        return us(float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], text=True)))

    def copy_refs(seg):
        new_refs = []
        for ref in seg.get("extra_material_refs", []):
            for key, items in dm.items():
                if isinstance(items, list):
                    hit = next((m for m in items if isinstance(m, dict) and m.get("id") == ref), None)
                    if hit:
                        c = json.loads(json.dumps(hit))
                        c["id"] = uid()
                        mats.setdefault(key, []).append(c)
                        new_refs.append(c["id"])
                        break
        seg["extra_material_refs"] = new_refs

    # Video: one clip per scene and card, cloned from the seed clip.
    video = next(t for t in d["tracks"] if t["type"] == "video")
    seed = video["segments"][0]
    seed_mat = next(m for m in mats["videos"] if m["id"] == seed["material_id"])
    video["segments"], mats["videos"] = [], []
    for scene in plan["scenes"]:
        path = os.path.join(fit, scene["file"])
        mat = json.loads(json.dumps(seed_mat))
        mat.update(id=uid(), path=path, material_name=scene["file"], duration=probe(path), has_audio=False)
        mats["videos"].append(mat)
        seg = json.loads(json.dumps(seed))
        dur = us(scene["end"] - scene["start"])
        seg.update(id=uid(), material_id=mat["id"], target_timerange={"start": us(scene["start"]), "duration": dur},
                   source_timerange={"start": 0, "duration": min(dur, mat["duration"])})
        video["segments"].append(seg)
    pushes(d, plan)

    # Narration, by line order, and the sting on the cards that ask for it.
    kinds = {a["id"]: a["type"] for a in mats["audios"]}
    audio_tracks = [t for t in d["tracks"] if t["type"] == "audio"]
    lines = sorted((s for t in audio_tracks for s in t["segments"] if kinds.get(s["material_id"]) == "text_to_audio"),
                   key=lambda s: s["target_timerange"]["start"])
    if len(lines) != len(plan["narration_at"]):
        sys.exit(f"expected {len(plan['narration_at'])} narration lines, found {len(lines)}")
    for seg, at in zip(lines, plan["narration_at"]):
        seg["target_timerange"]["start"] = us(at)
    donor_audio = {a["id"]: a for a in dm["audios"]}
    donor_sting = next(s for t in donor["tracks"] if t["type"] == "audio" for s in t["segments"]
                       if donor_audio[s["material_id"]]["type"] == "extract_music")
    sting_mat = json.loads(json.dumps(donor_audio[donor_sting["material_id"]]))
    sting_mat["id"] = uid()
    mats["audios"].append(sting_mat)
    stings_new = []
    for card in plan["cards"]:
        if card.get("sting"):
            seg = json.loads(json.dumps(donor_sting))
            seg["id"] = uid()
            seg["material_id"] = sting_mat["id"]
            seg["target_timerange"] = {"start": us(card["start"]), "duration": donor_sting["target_timerange"]["duration"]}
            copy_refs(seg)
            stings_new.append(seg)
    audio_tracks[0]["segments"] = sorted(lines + stings_new, key=lambda s: s["target_timerange"]["start"])
    d["tracks"][:] = [t for t in d["tracks"] if t["type"] != "audio" or t is audio_tracks[0]]

    # Captions: the donor's word-highlight template, with the post's exact words.
    dtemplates = {t["id"]: t for t in dm["text_templates"]}
    dtexts = {t["id"]: t for t in dm["texts"]}
    dcap_track = next(t for t in donor["tracks"] if t["type"] == "text" and t["segments"] and t["segments"][0]["material_id"] in dtemplates)
    dseg = dcap_track["segments"][0]
    dtpl = dtemplates[dseg["material_id"]]
    dtxt = dtexts[dtpl["text_info_resources"][0]["text_material_id"]]
    text_tracks = [t for t in d["tracks"] if t["type"] == "text"]
    cap_track = text_tracks[0]
    cap_track["segments"] = []
    d["tracks"][:] = [t for t in d["tracks"] if t["type"] != "text" or t is cap_track]
    mats["texts"], mats["text_templates"] = [], []
    mats["material_animations"] = []
    render = 14000
    for cap in plan["captions"]:
        parts = caption_chunks(cap["text"])
        begin, span = cap["at"] + cap["from"], cap["to"] - cap["from"]
        total = sum(len(p) + 1 for p in parts)
        for part in parts:
            length = span * (len(part) + 1) / total
            dur = us(length)
            txt = json.loads(json.dumps(dtxt))
            txt["id"] = uid()
            content = json.loads(txt["content"])
            content["text"] = part
            content["styles"] = content["styles"][:1]
            content["styles"][0]["range"] = [0, len(part)]
            txt["content"] = json.dumps(content, ensure_ascii=False)
            txt["recognize_text"] = part
            words, st, en, at = [], [], [], 0
            pieces = part.split()
            weight = sum(len(w) + 1 for w in pieces)
            for i, w in enumerate(pieces):
                share = (len(w) + 1) / weight * length * 1000
                start_ms = round(at)
                end_ms = round(at + share)
                words.append(w); st.append(start_ms); en.append(end_ms)
                at += share
                if i < len(pieces) - 1:
                    words.append(" "); st.append(end_ms); en.append(end_ms)
            txt["words"] = {"start_time": st, "end_time": en, "text": words}
            mats["texts"].append(txt)
            tpl = json.loads(json.dumps(dtpl))
            tpl["id"] = uid()
            res = tpl["text_info_resources"][0]
            res["id"] = uid()
            res["text_material_id"] = txt["id"]
            res["attach_info"]["duration"] = dur
            seg = json.loads(json.dumps(dseg))
            seg["id"] = uid()
            seg["material_id"] = tpl["id"]
            seg["target_timerange"] = {"start": us(begin), "duration": dur}
            seg["render_index"] = render
            render += 1
            copy_refs(seg)
            for a in mats["material_animations"]:
                if a["id"] in seg["extra_material_refs"]:
                    for item in a["animations"]:
                        item["duration"] = dur
            res["extra_material_refs"] = list(seg["extra_material_refs"])
            mats["text_templates"].append(tpl)
            cap_track["segments"].append(seg)
            begin += length

    # Cards, typed on with the donor's animation.
    card_track(d, plan)
    cards = d["tracks"][-1]
    dtyper = next(a for a in dm["material_animations"] if any(x.get("name") == "Retro Typer" for x in a["animations"]))
    for seg, card in zip(cards["segments"], plan["cards"]):
        mat = next(m for m in mats["texts"] if m["id"] == seg["material_id"])
        content = json.loads(mat["content"])
        for style in content["styles"]:
            style["size"] = plan["card_size"]
        mat["content"] = json.dumps(content, ensure_ascii=False)
        anim = json.loads(json.dumps(dtyper))
        anim["id"] = uid()
        for a in anim["animations"]:
            a["duration"] = us(plan["card_typing"])
        mats["material_animations"].append(anim)
        seg["extra_material_refs"] = [anim["id"]]

    # Filter and grain across the whole cut, under the text.
    for kind, key in (("filter", "effects"), ("effect", "video_effects")):
        src = next(t for t in donor["tracks"] if t["type"] == kind)
        seg = json.loads(json.dumps(src["segments"][0]))
        mat = json.loads(json.dumps(next(m for m in dm[key] if m["id"] == seg["material_id"])))
        mat["id"] = uid()
        if kind == "filter":
            mat["value"] = plan["filter_strength"]
        for param in mat.get("adjust_params") or []:
            if param.get("name") in plan.get("grain_params", {}):
                param["value"] = plan["grain_params"][param["name"]]
        mats.setdefault(key, []).append(mat)
        seg.update(id=uid(), material_id=mat["id"], target_timerange={"start": 0, "duration": us(plan["total"])})
        track = dict(src, id=uid(), segments=[seg])
        d["tracks"].append(track)

    order = {"video": 0, "filter": 1, "effect": 2, "text": 3, "audio": 4}
    d["tracks"].sort(key=lambda t: order.get(t["type"], 5))
    for index, track in enumerate(d["tracks"]):
        for seg in track["segments"]:
            seg["track_render_index"] = index
    d["duration"] = us(plan["total"])
    text = json.dumps(d)
    project = json.load(open(os.path.join(base, "Timelines", "project.json")))
    timeline = os.path.join(base, "Timelines", project["main_timeline_id"])
    for folder in (base, timeline):
        for name in ("draft_info.json", "draft_info.json.bak", "template-2.tmp"):
            with open(os.path.join(folder, name), "w") as f:
                f.write(text)
    with open(os.path.join(base, "draft_content.json"), "w") as f:
        f.write(text)
    print("built", draft, [(t["type"], len(t["segments"])) for t in d["tracks"]])


if __name__ == "__main__":
    {"open": open_draft, "finish": finish, "polish": polish, "build": build}[sys.argv[1]](*sys.argv[2:])
