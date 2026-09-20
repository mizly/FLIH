Fly-gym environment performance audit — 2026-09-20

Measured on this Jetson's NVIDIA Tegra Orin integrated GPU with MuJoCo 3.3.6,
Gymnasium 1.2.1, NumPy 1.26.1 and OpenCV 4.8.0. Each comparison used 10
environments, 10 warm-up steps/environment, then 100 measured steps/environment.
The loop steps environments sequentially, matching the trainer. Seeded checker
scenes contain 20 obstacles; actions are stationary. These are short environment
microbenchmarks with instrumentation overhead, excluding the teacher, RNN,
backpropagation, observation uploads and episode resets. They do not establish
the bottleneck of a training run on another machine. The system SciPy warns that
its supported NumPy range excludes the installed version; the probes completed.

| Check | Finding | Assessment |
| --- | --- | --- |
| `MUJOCO_GL` | Unset in the inspected shell; no repository configuration. MuJoCo 3.3.6 defaults to GLFW on Linux. Both explicit GLFW and EGL probes used NVIDIA. | Configuration opportunity: EGL achieved 87.1 aggregate environment steps/s versus GLFW's 76.6, about 14% higher throughput in this sample. GLFW was not falling back to CPU in the GPU-enabled probe. The actual training process's inherited environment was not inspected. |
| `glReadPixels` | Two synchronous RGB readbacks per environment step, through `Renderer.render()` → `mjr_readPixels()` → native `glReadPixels`. EGL's wrapper readback cost was 2.418 ms/step, 21.1% of wall time. | Significant cost, without an observed rendering exception. This timing includes 4× MSAA resolve and GPU waiting; it is not an isolated timing of the native `glReadPixels` function or memory copy. EGL does not eliminate readback. |
| Renderer/context recreation | Sensor `Renderer` is constructed once in `MuJoCoTwoCamEnv.__init__`. Its internal GL and `MjrContext` resources are reused. Human viewer `MjrContext` creation is guarded by `self.window is None`. | No hot-loop recreation: zero measured Renderer or MjrContext constructions during 1,000 steps. Training uses `RENDER_MODE=None`, so the human viewer is inactive. |
| `mjv_updateScene` | Exactly two calls/step. EGL: 0.042 ms/step for the native scene update, 0.133 ms/step for both complete Python `update_scene` calls. Model has 30 geoms; scene contains 32. | Not a material bottleneck here: native scene updates were 0.37% of wall time. `_get_camera_matrix` can update the scene too, but the normal training step does not call it. |
| Camera cadence | Each `env.step()` advances 10 × 0.002 s physics substeps, then `_get_obs()` renders both cameras. Verified 2,000 camera renders and 10,000 physics steps over 1,000 environment steps. | Already matches the clarified requirement: fresh images every environment step, nominally 50 Hz simulated time. No camera FPS timer or sleep. Cadence left unchanged. |

EGL time breakdown (milliseconds per environment step; nested rows must not be
added together):

| Component | ms/step | Wall time |
| --- | ---: | ---: |
| Entire environment step | 11.468 | 99.9% |
| Both `Renderer.render()` calls, including draw/readback/context handling | 3.252 | 28.3% |
| Readback alone, included above | 2.418 | 21.1% |
| Ten physics steps | 2.017 | 17.6% |
| LiDAR sample/hold, amortized | 1.346 | 11.7% |
| Two image resizes | 0.941 | 8.2% |
| Extra `mj_forward` | 0.184 | 1.6% |
| Both Python scene updates | 0.133 | 1.2% |
| Native scene updates, included above | 0.042 | 0.4% |

The images reaching the policy are 128×128, but each camera actually renders
240×135 to preserve the physical 16:9 view before resizing. The offscreen buffer
is 640×480 with 4× MSAA. These are useful follow-up experiments (smaller buffer,
less antialiasing, faster resize), but changing resolution/aspect/filtering can
change observations and should be checked against existing policies.

A separate `--finish-before-read` diagnostic took 14.224 ms/step: `glFinish`
cost 2.030 ms/step and subsequent `mjr_readPixels` still cost 2.541 ms/step.
Forcing completion did not remove the readback cost and made the loop slower.
This does not separate native transfer from MSAA resolve, which happens inside
`mjr_readPixels` after the diagnostic finish. Do not add `glFinish` to training.

Other candidates identified in the training path:

- LiDAR casts 667 rays using a Python loop and scalar `np.clip` at 6 Hz simulated
  time. There were 80,040 ray calls (120 full scans) in the measured 1,000 steps.
  Batching ray queries and clipping deserves measurement while preserving the
  existing sample-and-hold schedule and geometry filtering.
- `N_ENVS=10` does not parallelize simulation: `rollout_and_collect_balanced` steps
  environments one after another. The 87.1 steps/s figure is aggregate, not per
  environment. The RNN is batched, but simulation and retinal preprocessing are
  sequential.
- Camera arrays are uploaded to the policy device per environment; processed
  input is copied back with `.cpu().numpy()` per environment. Measure those
  synchronizations, teacher planning and RNN forward/backward separately before
  attributing the whole training slowdown to the simulator.

For Linux headless training, an explicit EGL launch is a reasonable next step:

```bash
cd fly-gym
MUJOCO_GL=egl python train_connectome_rnn_dagger.py
```

Set it before importing MuJoCo. EGL is a Linux choice in the inspected bindings;
do not apply this command blindly to the Windows setup. Check the reported GL
vendor/device, not just the environment variable: the restricted sandbox probe
initially fell back to Mesa llvmpipe when NVIDIA device access was denied. Only
GPU-enabled NVIDIA runs were used in the table above.

Reproduce with `profile_environment.py --backend egl --envs 10 --steps 100`, then
run a separate process with `--backend glfw`. Full results are in
`environment_profile_results.json`. The profiler needs the existing simulation
dependencies and PyOpenGL. Dependencies for this audit were installed only under
`/tmp/flih-sim-audit`; production environment/trainer code was not changed.

Relevant code: environment initialization at
`environment/mujoco_two_cam_env_random_obstacles.py:131`, stepping at `:351`,
human context at `:474`, cameras at `:559`, LiDAR at `:563`; sequential training
rollout at `train_connectome_rnn_dagger.py:734`, device uploads at
`core/utils.py:345`, and processed input readbacks at
`train_connectome_rnn_dagger.py:786`.

Upstream implementation checked against the benchmark version:
[backend selection](https://github.com/google-deepmind/mujoco/blob/3.3.6/python/mujoco/gl_context.py),
[Python renderer](https://github.com/google-deepmind/mujoco/blob/3.3.6/python/mujoco/renderer.py),
[native pixel readback and MSAA resolve](https://github.com/google-deepmind/mujoco/blob/3.3.6/src/render/render_gl2.c).
