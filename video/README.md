# FLIH motion showcase

## Kinetic alternate / FEVER

Latest export: `out/FLIH-v3-kinetic-fever.mp4`. Composition: `FLIH-Kinetic`.
1920 x 1080, 60 fps, 1,021 frames (17.017 seconds). The original `FLIH` composition and earlier exports remain available.

```powershell
npm run dev -- --no-open
npm run render:kinetic
```

This alternate uses the supplied **BUCKSHOT & FAKEMINK - FEVER** track at the user's specified **115 BPM**, at original playback speed. Copy the supplied MP3 to `public/fever.mp3` to restore it on another checkout; it is ignored by Git. Audio starts at source **3.500s**, fades in over **0.700s**, and fades out over the last **0.683s**. The first full FLIH reveal lands at source **8.000s**, composition **4.500s / frame 270**. An outlined FLIH wordmark becomes the filled wordmark at that exact cut.

After the reveal, cuts use `270 + round(beat * 3600 / 115)` to prevent rounding drift:

| Scene | Start frame | Video time | Music time |
| --- | ---: | ---: | ---: |
| Typographic build-up | 0 | 0.000s | 3.500s |
| FLIH reveal | 270 | 4.500s | 8.000s |
| Campus route | 333 | 5.550s | 9.050s |
| Queue confirmation | 427 | 7.117s | 10.617s |
| Fly brain footage | 489 | 8.150s | 11.650s |
| Illustrated camera POV | 614 | 10.233s | 13.733s |
| Comic impact | 708 | 11.800s | 15.300s |
| Plan / Queue / Drive | 771 | 12.850s | 16.350s |
| Closing FLIH title | 865 | 14.417s | 17.917s |

Visual direction references the kinetic typography and geometric motion in [stcubing's homepage](https://stcubing.com/#title), particularly [say it back](https://stcubing.com/portfolio/sayitback.html) and [unlucky number](https://stcubing.com/portfolio/unluckynumber.html). All graphics in the alternate are built locally; no reference video is incorporated. The design uses Anton display type, Space Grotesk supporting type, a restrained ink/ivory/coral/lime palette, generous text margins, directional wipes, iris bridges, and a position-and-size matched circle between the route and queue scenes. Fonts and their OFL licenses are bundled in `public/fonts/`.

Source lives in `src/kinetic/`, with one file per scene. Camera imagery remains an illustrated simulation. The fly-brain clip is the existing user-supplied footage, muted under FEVER.

Validation: ESLint and TypeScript, full H.264/AAC export, extracted scene and cut-point frames, stream metadata, and decoded audio timing/fade checks. Contact sheet: `out/kinetic-fever-storyboard.jpg`.

The final MP4 contains exactly 1,021 picture frames. Its AAC stream extends the container to 17.067s. Cross-correlation against the source trim measured approximately 66ms of decoded audio offset; the reveal remains within the requested approximate 8s music cue. After accounting for that offset, the central soundtrack correlates at 0.989 with the source and retains the intended 0.9 gain; opening and closing windows confirm both fades.

## Original 15-second version

15-second, 1920 x 1080, 30 fps Remotion composition with the supplied soundtrack.

## Preview and render

```powershell
cd video
npm install
npm run dev
npm run render
```

Composition: `FLIH`. Export: `out/FLIH-15s.mp4`.

The local soundtrack is `public/soundtrack.mp3` (ignored by Git). To restore it on another checkout, copy your original `hit the quan - gingus - Topic (128k).mp3` there. The video uses its first 15 seconds at original speed with a short ending fade.

## Timing

191 BPM, 30 fps: each beat is 9.4241 frames. Eight-beat cuts are rounded from cumulative beat positions, at frames 75, 151, 226, 302, and 377. The last scene ends at frame 450 for exactly 15 seconds of picture. AAC encoder padding can add approximately 61 ms to the MP4 container duration. Audio onset analysis found prominent transients near 2.514, 5.027, and 7.541 seconds, consistent with the chosen cut grid; 191 BPM remains the supplied tempo assumption.

## Scenes

- Meet FLIH and its wheeled fly mascot.
- Indoor campus route planning (schematic demo route).
- Join the guide queue without an account.
- Controlled by a real fly brain: supplied Beat Saber footage, source 11.0?13.53 seconds, muted under the music.
- FLIH CAM: simulated stereo POV, animated WASD inputs, two bumps, range and LiDAR warnings, red impact glow, and a comic explosion.
- Tiny brain, big campus.

Scenes are separate components in `src/scenes/`; timing and audio are in `src/Composition.tsx`; shared colors and animation helpers are in `src/design.tsx`. The mascot is copied from the app. Fonts are bundled locally.

Built following https://www.remotion.dev/docs and its agent skills, installed in the repository's `.agents/skills/` folder. Existing application files are unchanged.

Validation: ESLint and TypeScript; full H.264 render; six extracted scene previews inspected; ffprobe verified 1920 x 1080, 30 fps, H.264 picture and AAC audio. `out/storyboard.png` contains the scene overview.

## Revised export

`out/FLIH-15s-v2.mp4` contains the requested fly-brain and FLIH CAM replacements. The earlier export is retained. Copy `fly_brain_beat_saber.mp4` from the repository root into `video/public/` to restore the local clip on another checkout. The POV and readings are illustrated simulations. Impacts occur at local frames 19, 38, and 57 of the FLIH CAM scene, approximately every two beats. The soundtrack and overall 15-second timing remain unchanged.
