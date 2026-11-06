---
name: story-video
description: Turn a text post into a short vertical video told as a story, in a cold crime-show style, using image-generated scenes, narration and a CapCut desktop edit. Use when someone wants a narrated video version of a written post, thread or fact, or a series of them. No AI video generators.
---

# Story video

Makes a 45 to 65 second vertical video from a text post. The post's own words are the narration. The pictures, cards and pacing make it a story.

See the finished videos on the [a/foodusa Wall](https://abstracts.co/a/foodusa/wall).

## NEVER update CapCut

**Never update CapCut, no matter what.** Not to fix a bug, not to get a feature, and not because a dialog asks. These scripts edit CapCut's project files directly, and they were only tested on CapCut 9.6 for macOS.

CapCut shows a "Version update" window at launch and an "Update available" button on its home screen. Close the window with its close button. Never click **Update now** or **Update available**. If a task seems to need an update, stop and tell the person instead.

## Tools

- **Image generation:** an agent that can generate images. We used Codex with one agent per scene, at xhigh effort.
- **CapCut desktop for macOS:** signed in. The voice, filter, grain and text animation named here are Pro items, and any similar ones work. Remove-watermark is Pro too.
- **The [capcut MCP server](https://github.com/JmsLdrn/capcut-mcp):** optional for this flow, because the scripts in `scripts/` write the project directly.
- **Computer use:** for what CapCut only offers in its app, which is text to speech and export.
- **`ffmpeg` and Python 3.**

Set up a folder for each video:

```text
<post-dir>/
  brief.md           style and rules for the scene agents (examples/brief.md)
  lines.txt          narration, one line per paragraph (examples/lines.txt)
  timeline.json      the edit plan (examples/timeline.json)
  audio/             narration WAVs
  assets/            scene-01.mp4 and so on
```

## Steps

### 1. Read the source

Get the post's full text. **The post is the content.** The video turns it into a story people can watch. It doesn't rewrite it.

- Don't reword, soften or fact-correct its claims, and don't add lines of your own.
- Don't add the other side of a dispute unless the post has it.
- If something looks clearly wrong, tell the person once and let them decide. Leave the words alone.
- Link the original post and credit its author on screen.

### 2. Split it into a story

Split the post's sentences into narration lines, in its order. Only change how a number is written, so the voice reads it correctly: spell it out in `lines.txt` and use digits in the captions.

The person may trim lines. Plain words matter: if a line sounds like jargon or says nothing, flag it to them.

The storytelling comes from everything around the words: where the pictures change, where the cards fall, where the voice pauses, and which moment gets the sting.

### 3. Design one picture per beat

Write `brief.md` first and give it to every scene agent.

- No words, numbers or logos in the images. CapCut adds all type.
- Never reproduce a real brand's logo or label. Use generic packaging.
- Show proportions to scale, and count anything the narration counts.
- Build any map from real data, such as Natural Earth, never a generated map.
- Every scene has real motion inside it. A zoom on a still doesn't count.
- Don't use AI video generators or video services. Licensed real footage or photos are fine where they help. Record the source and license of each, credit it where the license asks, and never present a generated image as a real photo.

### 4. Make the scenes

Start all scene agents at once, each with one narration line and a paragraph on what we see and what moves. For your first video, make one scene first, so its look can guide the rest.

**How to make a GIF.** Asking an image model for a GIF returns a still. What works is generating photographic plates of the same subject in different states, then animating between them with code. Each agent delivers a `.gif`, a 1080x1920 H.264 master, and start and end frames. The edit uses the master, because GIF's 256 colors band.

**Review every scene yourself at phone size (about 390 px wide).** Automated checks can pass on a shot that doesn't work. A measured quarter of a pile of hazelnuts passed every check while looking like a flat disc of beads, and a correct comparison of 14 against 26 was too thin to see. Ask: does it read instantly on a phone? Send it back if not, then look again.

### 5. Generate the narration

1. In CapCut, use File > New Project, then close the project back to the home screen.
2. Run `scripts/capcut_draft.py prep <draft> <any.mp4> <any.wav>`, then `lines <draft> lines.txt`, then `sync <draft>`. `<draft>` is the project's name. This puts each line on the timeline as text, on a 9:16 canvas.
3. Open the project. For each line: click its text, open **Text to speech**, pick a voice (we use Marcus), and click **Generate speech**.
4. Copy the WAVs from the project's `textReading/` folder to `audio/`, oldest first, and name them in order.

The clip you just generated stays selected, and CapCut shows other tabs when two things are selected. Empty-space clicks don't reliably clear it. So click the next line's text, click the last audio clip to deselect it, and confirm the Text to speech tab is showing before you generate. New audio tracks also move the text row up, so read the timeline again each time. If Project settings opens, click Cancel.

Then find the pauses, which give you the caption timing and scene cuts:

```bash
ffmpeg -i line-01.wav -af silencedetect=noise=-38dB:d=0.12 -f null -
```

### 6. Write the plan

Fill in `timeline.json`, following `examples/timeline.json`:

- **`narration_at`:** where each line starts, in order.
- **`scenes`:** each clip's slot. `fit` is `speed` to fill the slot with the whole clip, `hold` to play it and hold the last frame, or `slow` to slow the action. `push` is a slow zoom. A long line shouldn't sit on one shot, so split it at a sentence break.
- **`cards`:** white text on black. Leave gaps in the narration for them.
- **`captions`:** the post's exact words with digits, timed from the pauses. Add up the text and compare it with the post: they should match word for word.
- **`donor_draft`:** a finished project to copy styles from (step 7).

Run `scripts/fit_scenes.py <post-dir>`. It retimes each scene to its slot in `assets/fit/` and makes the black card clip.

### 7. Assemble

CapCut 9.x on macOS reads `draft_info.json`. Never write it while a `.locked` file exists in the project's folder, because autosave would overwrite your edit. Start the write as a background job that waits for the lock to clear, then close the project:

```bash
while [ -e "<project folder>/.locked" ]; do sleep 0.1; done; python3 scripts/cut.py build "<draft>" timeline.json
```

`cut.py build` lays out scenes, cards, captions and narration, and copies the caption style, sting, filter, grain and card typing from `donor_draft`. Reopen the project and check it.

**Your first video has no donor, so make one.** Use any finished cut of a video:

1. Place your clips and narration on the timeline, in the app or with `build`'s layout as a guide.
2. Add auto captions from the Captions panel, and pick a caption style. We use a word-highlight style in white and yellow.
3. Import your sting sound and put it on the timeline once.
4. Add a cold filter (we use Cold Fog City) and a grain effect (we use Gloom Grain).
5. Add a card as text on the timeline, with the Retro Typer text animation.

That project can then be the donor for every later video. Keep it. `build` looks for that exact animation name, so change the name in `cut.py` if you pick a different one.

### 8. Check the export

Export from CapCut, then review the exported file, not the editor preview.

- Pull frames at phone size across the whole video, and listen with the sound on.
- Measure loudness with `ffmpeg -af ebur128`.
- Compare brightness against the source clips. Filters and effects stack: at full strength they took one video to a quarter of its brightness and hid what the narration described. Start a filter near 25 to 35%, and build scenes bright enough to survive it.
- A position keyframe can expose a bright bar at the frame's edge. Use scale alone.

### 9. The look: crime procedural

- **Title cards:** white text on black, each marking a jump in the story. Use a flared typeface such as Optima, at a size that stays clear of the screen edges, typed on over about a second.
- **The sting:** a "dun dun" hit right after the hook, plus at most one more at the biggest turn in the story. Don't overuse it. Other cards stay silent and shorter, about 1.5 seconds.
- **Grade:** a cold filter at low strength, light film grain, and hard cuts.
- **Cards come from the post:** only names, places, dates or phrases the post itself gives. Don't add "guilty" or "case closed," because the format already implies wrongdoing.
- **When the post is good news:** make it the twist. Keep the investigation mood, then let the lights come up on the last line.
- **Rights:** don't use a real show's name or logo. Bring your own sting sound, and know that a real show's sound belongs to its rights holders, so a platform may mute or flag it.

### 10. Publish on Abstracts

Abstracts takes MP4 and WebM up to 50 MiB. CapCut's "mp4" export is really a QuickTime file with an `.mp4` name, which Abstracts refuses with "Use PNG, JPEG, GIF, MP4 or WebM files." Fix it with a rewrap, which keeps the quality:

```bash
ffmpeg -i export.mp4 -map 0 -c copy -movflags +faststart -brand isom -f mp4 video-for-abstracts.mp4
```

A minute of 720p often comes out over the limit. If it does, re-encode with a two-pass ffmpeg encode at about 5.5 to 6.7 Mb/s video, copy the audio as is, and add the same three options.

1. Show the finished video to the person whose account it goes on, and wait for their OK.
2. Read the Wall right before posting (`https://abstracts.co/a/<slug>.json`). If that post's link is already there, don't post it again.
3. Post the link to the original post as the text, with the video attached. This goes through the website composer, because the MCP server can't attach plain video yet.
4. Click Post once. Large uploads can drop a browser connection, so read the Wall for the result before doing anything else.

Posts always go out under the person's own account. A post made through the website shows the website badge, even if an agent did the clicking, so an agent posting for someone should tell them that first.

## Computer use on a shared desktop

The person may be using the same machine.

- Don't switch apps for them, or send input to windows you didn't open.
- Keep each computer-use call short, and check the result after each one. Long loops get interrupted and fail halfway.
- With CapCut in the background, its floating EditPilot panel can take accessibility focus, so window buttons don't respond and coordinates can land on the wrong control. Don't click blind. Dismissing a dialog with its Cancel button often returns focus to the main window. If it doesn't, ask the person to close the project, and wait for the `.locked` file to go away.
- Export-menu choices such as resolution may not respond in the background. Ask the person to set them once.
- A background export can finish writing but sit in the Export dialog. The file is in a hidden `.__capcut_export_temp_folder_*` folder next to the destination. If its size stops changing and it decodes, copy it.
- Never grant the screen-recording permission CapCut can ask for. Click Cancel.
- If the person is using the app, stop and ask. They can often click through a step faster than you can.
