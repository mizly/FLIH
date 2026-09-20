# Low-rate camera and LiDAR captions for live chat

## Decision

It is feasible to add an **advisory, low-rate perception path** for the hackathon
live-chat feature. This path is separate from the fly-gym vision policy: fly-gym
continues to handle driving, while this path occasionally packages the latest two
camera views, approximate object labels, and approximate LiDAR ranges for a
multimodal language model.

The intended rate is about **one update every 1-2 seconds**, and it may be slower if
the remote model has an outstanding request. It is not a safety system and its
output must not be used for collision avoidance or motor control.

## Why it fits on this Jetson

This robot is an 8 GB Jetson Orin Nano Super. The smallest YOLO26 detector
(`YOLO26n`) is approximately 2.4 million parameters and 5.5 billion operations for
one 640x640 image. Published Ultralytics measurements for this Jetson put an FP16
TensorRT inference at about 4.57 ms per image, before pre/post-processing.

At one caption update per second, two camera views therefore cost approximately:

| Work | Approximate cost at 1 update/s |
| --- | ---: |
| Two 640x640 YOLO26n inputs | 11 billion operations/s |
| Published TensorRT inference time for both | 9.1 ms/s |
| Rectifying two frames at the measured 12 ms/frame | 24 ms of one CPU core/s |
| Projecting one 667-point scan into both cameras and testing 20 boxes | under 1 ms of one CPU core/s in a synthetic local test |

Those are small loads. If each 640x360 camera is padded only to the detector stride
and processed as 640x384, the detector work is lower still. At this rate, however,
the choice between square, rectangular, batched, or sequential inference is not
important to feasibility. Use one FP16 TensorRT engine for both images; do not load
one model per camera.

The dominant delay will normally be JPEG preparation, network transit, and remote
multimodal-model inference, which may take hundreds of milliseconds or several
seconds. Do not queue perception requests faster than the service completes them.

## Input arrangement

"One YOLO" does not require joining the cameras into one image. Load one engine and
reuse it for both views. A conventional 1280x360 side-by-side image squeezed into a
640x640 detector input would reduce each camera to about 320x180 useful pixels and
make small objects harder to identify.

The practical choices are:

- Process two 640x384 views sequentially through one engine. This has the lowest
  peak activation memory and is recommended at the one-update-per-second target.
- Use a batch of two 640x384 views. This may improve throughput but retains two sets
  of input/activation buffers, which is unnecessary at this low rate.
- Use one 1280x384 composite, preserving approximately 640x360 per camera. Its raw
  convolution work is similar to the two rectangular views combined, while seam
  handling and coordinate conversion are more complicated.

The sequential option adds only milliseconds and keeps the left/right coordinate
systems independent.

## RAM budget

Jetson CPU and GPU allocations share the same 8 GB of physical memory. The model's
engine file is small, but TensorRT contexts, CUDA libraries, activations, and
workspace consume more memory than the weights alone.

| Component | Approximate memory |
| --- | ---: |
| Two raw 1640x1232 BGR capture frames | 11.6 MiB |
| Frame copies, rectification maps, and temporary images | roughly 20-50 MiB |
| Two rectified 640x360 BGR frames | 1.3 MiB |
| One 640x384 FP16 input tensor | 1.4 MiB |
| YOLO26n FP16 TensorRT engine file | about 8.1 MB on disk |
| LiDAR scan, clusters, evidence JSON, and JPEGs | well under 10 MiB |
| TensorRT/CUDA context, activations, and workspace | implementation-dependent; budget roughly 200-500 MiB |

A lean process that uses TensorRT directly and reuses preallocated buffers should be
budgeted at approximately **300-700 MiB of additional steady-state memory**. Keeping
the full Ultralytics/PyTorch Python runtime loaded may instead add roughly **0.8-1.5
GiB**; that range is an engineering allowance, not a measurement on this installation.
The exact peak must be recorded after building the final engine.

A system snapshot during this feasibility review showed 7.4 GiB usable RAM, 5.2 GiB
used, and about 2.0 GiB available. Linux can reclaim some file cache, but the lean
TensorRT route leaves much more margin for the web server, camera processes, and
fly-gym controller. Swap is not a substitute for GPU-accessible unified memory and
may create long latency spikes.

RAM recommendations:

- Keep one engine and one execution context, not one per camera.
- Process the cameras sequentially at this low rate.
- Reuse host and device buffers rather than allocate them on every update.
- Retain only the newest frames, scan, evidence object, and optional caption.
- Run the large multimodal model remotely; do not load it on the Jetson.
- Measure process RSS and `tegrastats` before and during inference, including the
  first inference when TensorRT may allocate lazily.

## Proposed data flow

```text
latest left frame (sensor-id 1) ----\
                                      shared YOLO engine --> detections --\
latest right frame (sensor-id 0) ---/                                  |
                                                                         +--> evidence JSON
latest complete 2D LiDAR turn --> clusters --> project into each view --/         +
                                                                                    |
left/right image or side-by-side annotated JPEG ------------------------------------+
                                                                                    |
                                                                                    v
                                                                       multimodal chat model
```

Reuse the newest-frame behavior in `backend/csi_camera.py` and the newest-turn
behavior in `backend/lidar.py`. The caption worker should sample these in memory;
it should not receive the WebSocket JPEGs and decode them again.

For each update:

1. Take the newest rectified frame from each working camera and the newest complete
   LiDAR turn.
2. Run the two frames through one detector, either sequentially or as a batch of two.
3. Split adjacent LiDAR returns into simple range/angle clusters.
4. Transform cluster points from the LiDAR frame into each camera frame and project
   them to pixels.
5. Associate a detection with a cluster when projected points fall inside its box.
   Use the cluster median or nearest credible return as an approximate surface range.
6. Produce both an image and compact structured evidence. For example:

   ```json
   {
     "captured_at": "...",
     "left": [
       {"label": "person", "confidence": 0.86, "distance_m": 1.8},
       {"label": "chair", "confidence": 0.72, "distance_m": null}
     ],
     "right": [
       {"label": "door", "confidence": 0.68, "distance_m": 3.1}
     ],
     "lidar_age_ms": 74
   }
   ```

7. Give the multimodal model the image plus this JSON as **fallible sensor hints**.
   Structured text is preferable to relying on the model to read distance text
   painted into the JPEG. An annotated JPEG remains useful for the demo UI.

## Scheduling for chat

Use a single-flight worker:

- Keep only the newest sensor sample; never build a backlog.
- If a model request is still running, skip the next periodic update.
- Cache the latest evidence/image bundle for chat.
- Prefer calling the remote multimodal model when a chat message arrives. A
  background caption every 2-5 seconds can be used when the UI needs unsolicited
  scene updates.
- Attach capture time and evidence age so the chat layer can say when its view is
  stale.

This makes a one-second sampling rate possible without requiring one paid remote
request every second.

## Calibration required before the demo

The calibration directory is currently empty. `backend/camera_geometry.py` is using
nominal IMX219 lens values and assumes zero distortion, so projected LiDAR points are
not yet trustworthy.

Before demonstrating distance labels:

1. Run `backend/calibrate_cameras.py` to obtain intrinsics for both physical camera
   modules at the deployed capture mode.
2. Determine a full six-degree-of-freedom transform from the LiDAR to each camera.
   Camera position alone is not enough; translation plus roll, pitch, and yaw are
   required. The stereo calibration only relates the cameras to each other.
3. Overlay projected points on live frames and manually verify several targets near
   the centre and edges of both views. For a hackathon prototype, a measured initial
   transform followed by visual adjustment is acceptable.
4. Add acquisition timestamps to camera frames. The LiDAR currently timestamps a
   completed revolution, while one 6 Hz revolution spans about 167 ms.

Perfect motion compensation is unnecessary for conversational captions, but grossly
misregistered points will make the text less credible.

## Expected limitations

A 2D LiDAR sees only one horizontal plane. It may hit a person's legs, pass under a
tabletop, miss a high object, see a wall through the empty part of a bounding box, or
get no useful return from glass. Consequently:

- Treat every distance as approximate and describe it as a nearest surface, not the
  object's centre.
- Use `null`/"unknown" when no coherent cluster matches; do not invent a range from
  the camera image.
- Prefer wording such as "a person is roughly 1.8 m away".
- Tell the multimodal model that YOLO labels and LiDAR associations may be wrong.
- Never expose these captions to the driving controller as obstacle measurements.

For the live-chat goal these limitations are acceptable: the raw images still let
the multimodal model understand the scene, while the detector and LiDAR provide
useful hints it could not reliably infer from a monocular image alone.

## Suggested proof-of-concept order

1. Calibrate the cameras and record a few paired frames and scans.
2. Implement offline projection overlays and tune the LiDAR-to-camera transforms.
3. Add low-rate YOLO inference and evidence JSON without any remote API call.
4. Review saved examples for obviously wrong object/range associations.
5. Connect the latest evidence bundle to the existing multimodal classification/chat
   client.
6. Measure end-to-end request latency and reduce the remote request rate if calls
   overlap.

The implementation should remain a separate optional process so a camera, detector,
or remote API failure cannot affect teleoperation or the fly-gym controller.

## External references

- [Ultralytics YOLO26 model sizes and operation counts](https://docs.ultralytics.com/models/yolo26/)
- [Ultralytics Jetson deployment guide and Orin Nano Super benchmarks](https://docs.ultralytics.com/guides/nvidia-jetson/)
