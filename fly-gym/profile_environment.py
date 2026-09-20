"""Measure the simulation without loading the connectome or changing its cadence.

Run separate processes for each backend, e.g.:
    python profile_environment.py --backend egl --envs 10 --steps 100
    python profile_environment.py --backend glfw --envs 10 --steps 100

Timings are inclusive: do not add parent and child rows. mjr_readPixels includes
framebuffer resolve and waiting for queued GL work, not just pixel transfer.
--finish-before-read is a diagnostic that moves some GPU waiting to glFinish;
it is deliberately NOT a training optimization.
"""
import argparse
from collections import defaultdict
from contextlib import ExitStack
import functools
import json
import os
import time
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("egl", "glfw", "osmesa"))
    parser.add_argument("--envs", type=int, default=1)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--finish-before-read", action="store_true")
    args = parser.parse_args()
    if min(args.envs, args.steps) < 1 or args.warmup < 0:
        parser.error("envs/steps must be positive and warmup nonnegative")
    if args.backend:
        os.environ["MUJOCO_GL"] = args.backend  # Must precede importing MuJoCo.

    import cv2
    import mujoco
    import numpy as np
    from OpenGL import GL
    from environment.mujoco_two_cam_env_random_obstacles import MuJoCoTwoCamEnv

    samples = defaultdict(list)

    def timed(name, function):
        @functools.wraps(function)
        def wrapped(*a, **kw):
            start = time.perf_counter()
            try:
                return function(*a, **kw)
            finally:
                samples[name].append(time.perf_counter() - start)
        return wrapped

    envs = []
    try:
        start = time.perf_counter()
        for i in range(args.envs):
            envs.append(MuJoCoTwoCamEnv(width=128, height=128,
                                      arena_half_extent=7, seed=42 + i,
                                      render_mode=None))
        init_seconds = time.perf_counter() - start
        env = envs[-1]
        metadata = {
            "mujoco": mujoco.__version__,
            "MUJOCO_GL": os.environ.get("MUJOCO_GL"),
            "context": type(env.renderer._gl_context).__module__,
            "gl_vendor": GL.glGetString(GL.GL_VENDOR).decode(),
            "gl_renderer": GL.glGetString(GL.GL_RENDERER).decode(),
            "envs": args.envs, "steps_per_env": args.steps,
            "warmup_per_env": args.warmup,
            "finish_before_read": args.finish_before_read,
            "initialization_seconds": init_seconds,
            "render_size": [env.camera_width, env.camera_height],
            "observation_size": [env.W, env.H],
            "offscreen_size": [env.model.vis.global_.offwidth,
                               env.model.vis.global_.offheight],
            "offscreen_samples": env.model.vis.quality.offsamples,
            "model_geoms": env.model.ngeom, "scene_geoms": env.renderer.scene.ngeom,
            "physics_timestep": env.model.opt.timestep,
            "frame_skip": env.frame_skip, "lidar_rays": env.lidar_config.num_rays,
        }
        # Match the trainer's sequential environment loop. Stationary actions
        # keep each seeded scene stable; terminal flags are ignored in this probe.
        action = np.zeros(2, dtype=np.float32)
        for _ in range(args.warmup):
            for env in envs:
                env.step(action)

        with ExitStack() as stack:
            targets = [
                (mujoco, "mj_step", "physics.mj_step"),
                (mujoco, "mj_forward", "physics.mj_forward"),
                (mujoco._functions, "mjv_updateScene", "scene.mjv_updateScene"),
                (mujoco.Renderer, "update_scene", "camera.update_scene"),
                (mujoco.Renderer, "render", "camera.render"),
                (mujoco._render, "mjr_render", "draw.mjr_render"),
                (mujoco._render, "mjr_readPixels", "readback.mjr_readPixels"),
                (cv2, "resize", "camera.resize"),
                (MuJoCoTwoCamEnv, "lidar_scan", "lidar.sample_or_hold"),
                (MuJoCoTwoCamEnv, "_get_obs", "observation.total"),
                (MuJoCoTwoCamEnv, "step", "step.total"),
                (mujoco.Renderer, "__init__", "creation.Renderer"),
                (mujoco._render, "MjrContext", "creation.MjrContext"),
            ]
            for owner, attr, name in targets:
                stack.enter_context(patch.object(owner, attr, timed(name, getattr(owner, attr))))
            # Count rays without a timer per ray, which would distort tiny calls.
            ray_count = 0
            original_ray = mujoco.mj_ray

            def ray(*a, **kw):
                nonlocal ray_count
                ray_count += 1
                return original_ray(*a, **kw)

            stack.enter_context(patch.object(mujoco, "mj_ray", ray))
            if args.finish_before_read:
                original_read = mujoco._render.mjr_readPixels
                finish = timed("diagnostic.glFinish", GL.glFinish)

                def read_after_finish(*a, **kw):
                    finish()
                    return original_read(*a, **kw)

                stack.enter_context(patch.object(mujoco._render, "mjr_readPixels", read_after_finish))
            start = time.perf_counter()
            for _ in range(args.steps):
                for env in envs:
                    env.step(action)
            elapsed = time.perf_counter() - start

        total_steps = args.steps * args.envs
        metadata.update(wall_seconds=elapsed, env_steps_per_second=total_steps / elapsed,
                        mj_ray_calls=ray_count,
                        renderer_creations=len(samples["creation.Renderer"]),
                        context_creations=len(samples["creation.MjrContext"]))
        result = {"metadata": metadata, "timings": {}}
        for name, values in sorted(samples.items()):
            if values:
                result["timings"][name] = {
                    "calls": len(values),
                    "mean_call_ms": float(np.mean(values) * 1000),
                    "p95_call_ms": float(np.percentile(values, 95) * 1000),
                    "ms_per_env_step": sum(values) * 1000 / total_steps,
                    "wall_percent": sum(values) * 100 / elapsed,
                }
        print(json.dumps(result, indent=2))
    finally:
        for env in reversed(envs):
            env.close()


if __name__ == "__main__":
    main()
