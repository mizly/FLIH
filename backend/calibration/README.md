# Camera calibration

What the lenses on *this* robot actually do, measured rather than assumed. Empty
until someone runs the calibration; `camera_geometry.py` falls back to the IMX219-77
spec sheet in the meantime and says so at startup.

The spec-sheet fallback models **zero distortion**, which is the one thing a real lens
definitely has. Everything the robot does with camera geometry is provisional until
these files exist.

```sh
python3 backend/calibrate_cameras.py                  # live, SPACE to grab a view
python3 backend/calibrate_cameras.py --no-preview     # headless, grabs on a timer
python3 backend/calibrate_cameras.py --from-dir shots # re-solve saved images
```

Print a checkerboard, mount it on something rigid and flat, and measure a square with
calipers rather than trusting the printer's scaling - a square size that is wrong by
2% puts the same error straight into the baseline. Work the board around the whole
frame, **corners included**: that is where distortion is largest, and a calibration
that only saw the middle of the image is worst exactly where it matters most. Twenty
or so varied views per camera is plenty; more near-identical ones add nothing.

## Files

| File | What it holds |
| ---- | ------------- |
| `camera_<sensor id>.json` | One camera's intrinsics and distortion, plus the capture size they were taken at |
| `stereo.json` | The pose of the left camera relative to the right: baseline and relative yaw |

**Commit them.** They describe these specific camera modules on this specific robot.
Swapping a module, or re-seating a lens in its thread, means recalibrating.

## The capture mode is part of the calibration

Sensor modes crop the array differently, so a calibration is only valid for the mode
it was taken at. The files record their capture size; `camera_geometry.intrinsics_for`
rescales between modes that share the full array and **refuses** one taken at a
cropped mode such as 1280x720, because that is a different view of the sensor rather
than a resized one. Calibrate at the mode you deploy.

## What this cannot measure

`stereo.json` gives the cameras' pose *relative to each other*. Where the pair sits on
the chassis - mount height above the floor and downward pitch - has to be measured
against the ground, because stereo calibration has no idea where the ground is.
fly-gym's nominal figures are 175 mm up, 5 deg down and 29.73 deg outward per camera
(`fly-gym/environment/robot_geometry.xml`), and those are drawing numbers, not
measurements of this robot.

Note that fly-gym's 29.73 deg outward was picked to give exactly 10 deg of binocular
overlap at the sim's 69.47 deg horizontal field of view. The real lens only reaches
62.2 deg, so the actual overlap is nearer **2.7 deg**. Restoring 10 deg would mean
physically re-aiming the cameras to 26.1 deg outward - a hardware change that would
then also make the sim wrong, so do not make it casually.
