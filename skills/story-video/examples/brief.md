# <video name>

Source post: <link> (<author>, <date>)

The narration is the post's own words (`lines.txt`). Don't change them.

## Style

- **Quality bar:** <paths to your best finished frames>. Match that realism and go further: this must look like a real photograph shot for a film, with visible movement doing the storytelling.
- **Look:** photorealistic macro photography in a cold, low-key crime-drama style. Dark charcoal background, one soft key light from upper left, subtle rim light, shallow depth of field. The subject's real colors pop against the cold surroundings.
- **Brightness:** dark, but never murky. The subject reads instantly on a phone at 390 px wide. The whole frame's mean brightness is at least 40 out of 255, because a color filter goes on top later.
- **Frame:** vertical 9:16, 1080x1920. Keep the subject between 20% and 72% of frame height. The top 15% and bottom 25% stay calm and dark for captions, with no hard edges or bands.
- **Text:** no words, numbers, logos or labels in the images. CapCut adds all type.
- **Brands:** never reproduce a real logo, label or package design. Everything is generic and unbranded.
- **People:** none, unless the person making the video asks for it.
- **Motion:** real motion inside the scene, eased and with weight, from the first second. A zoom or pan on a still doesn't count. No AI video generators or video services.

## Method

Asking an image model for a GIF returns a still. Generate consistent photographic plates of the subject in different states, then animate between them with code (Python, FFmpeg). Prefer many photographed elements moving over one plate cross-fading.

## Rules for every scene agent

- Work only in `assets/scene-NN/`, and put the finished files in `assets/`.
- Deliver `assets/scene-NN.gif` (at least 720x1280), `assets/scene-NN.mp4` (1080x1920, 30 fps, H.264 yuv420p, about 20 Mb/s), `assets/scene-NN-start.png` and `assets/scene-NN-end.png`.
- About 6 s long: motion starts within 0.3 s, with about a 1 s hold at the end. Say so in the task if a scene runs long in the edit.
- Before finishing, view decoded frames at 390 px wide and ask: would a viewer believe this is a real photograph, and does it read instantly? Passing a measurement doesn't count. Redo it if not: no warped shapes, flicker, CG-looking surfaces, stray text or logos, or hard horizontal bands.
- Count anything the narration counts, and report the count.
- List any real footage or photo you use, with its source and license.
- Remove temporary files and stop your processes. Report in under 5 lines.

## Scene task template

Read <path>/brief.md and follow it exactly. Make scene NN, under "<the narration line, word for word>".

<One paragraph: what we see, what moves, what the viewer should feel, and what the last frame holds on.>
