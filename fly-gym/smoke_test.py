"""Headless checks for the MuJoCo arena and analytic avoidance teacher."""

from pathlib import Path
import argparse
import sys

import numpy as np

from agents.teacher_analytic_agent import PlannerAnalyticTeacher
from environment.mujoco_two_cam_env_random_obstacles import MuJoCoTwoCamEnv


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=2)
    parser.add_argument("--steps", type=int, default=80)
    args = parser.parse_args()

    edge_path = Path("connectomes/drosophila adult connectome/connections_princeton.csv")
    if not edge_path.exists():
        print(f"[data] Connectome edge list not found: {edge_path}")
        print("[data] The simulator smoke test can run, but fly-brain training needs this file.")

    env = MuJoCoTwoCamEnv(
        width=64,
        height=64,
        max_episode_steps=args.steps,
        n_obstacles=12,
        arena_half_extent=7.0,
        render_mode=None,
        seed=123,
    )
    teacher = PlannerAnalyticTeacher(
        arena_half_extent=env.arena,
        cell_size=0.1,
        robot_radius=0.2,
        safety_margin=0.1,
        include_collision_flag=True,
    )

    try:
        for episode in range(args.episodes):
            obs, _ = env.reset(seed=123 + episode)
            teacher.reset()
            assert obs["cam_left"].shape == (64, 64, 3)
            assert obs["cam_right"].shape == (64, 64, 3)

            total_reward = 0.0
            for _ in range(args.steps):
                action = np.asarray(teacher.act(env), dtype=np.float32)
                assert action.shape == (2,)
                obs, reward, terminated, truncated, info = env.step(action)
                total_reward += reward
                if terminated or truncated:
                    break

            print(
                f"[episode {episode + 1}] steps={env._t} "
                f"dist_to_goal={info['dist_to_goal']:.2f} total_reward={total_reward:.3f}"
            )
    finally:
        env.close()

    print("[ok] MuJoCo cameras, observations, actions, and teacher loop are working.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
