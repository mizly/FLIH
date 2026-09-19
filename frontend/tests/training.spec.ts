import { test, expect } from "@playwright/test";
import type { TrainingSnapshot } from "../src/lib/training-types";

function fixture(): TrainingSnapshot {
  return {
    schema_version: 1,
    run_id: "test-run-12",
    started_at: Date.now() / 1000 - 160,
    updated_at: Date.now() / 1000,
    elapsed_seconds: 160,
    status: "running",
    phase: "optimizing",
    iteration: 2,
    episodes_in_iteration: 50,
    train_step: 25,
    environment_steps: 24000,
    episodes_total: 50,
    successes: 35,
    collision_episodes: 8,
    beta: 0.5,
    error: null,
    config: {
      model: "Connectome RNN · DAgger",
      iterations: 4,
      episodes_per_iteration: 50,
      train_steps: 300,
      environments: 10,
      learning_rate: 0.0003,
      batch_size: 64,
      max_episode_steps: 4000,
      lidar_rays: 667,
      lidar_rate_hz: 6,
      camera_size: [128, 128],
    },
    loss_history: Array.from({ length: 30 }, (_, i) => ({
      step: i + 1,
      iteration: 2,
      loss: 0.8 * Math.exp(-i / 10) + 0.02,
    })),
    episodes: Array.from({ length: 12 }, (_, i) => ({
      episode: i + 1,
      iteration: 2,
      reward: 2 + i * 0.8,
      steps: 350 + i * 3,
      success: i % 3 !== 0,
      collision: i % 4 === 0,
      distance: 0.4,
    })),
    iterations: [],
    checkpoints: [
      {
        name: "connectome_rnn_dagger_iter_1.pt",
        iteration: 1,
        saved_at: Date.now() / 1000 - 30,
      },
    ],
    buffer_counts: {
      straight: 350,
      turn: 220,
      collision: 75,
      pre_collision: 80,
      start: 40,
    },
  };
}

test("training dashboard handles waiting, live updates and disconnection", async ({
  page,
}) => {
  let run: TrainingSnapshot | null = null;
  let unavailable = false;
  await page.route("**/api/training", (route) =>
    route.fulfill({
      status: unavailable ? 503 : 200,
      json: unavailable ? { error: "unavailable" } : { run, stale: false },
    }),
  );
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/training");
  await expect(
    page.getByRole("heading", { name: "Ready when your model is." }),
  ).toBeVisible();
  run = fixture();
  await expect(page.getByRole("status")).toHaveText("Live training");
  await expect(page.getByText("70.0%", { exact: true })).toBeVisible();
  await expect(page.getByRole("img", { name: /Learning curve/ })).toBeVisible();
  run = { ...run, status: "completed" };
  await expect(page.getByRole("status")).toHaveText("Run completed");
  unavailable = true;
  await expect(page.getByRole("status")).toHaveText("Connection lost");
  await expect(page.getByText("70.0%", { exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test("training dashboard shows stale runs and fits a mobile viewport", async ({
  page,
}) => {
  const run = fixture();
  await page.route("**/api/training", (route) =>
    route.fulfill({ json: { run, stale: true } }),
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/training");
  await expect(page.getByRole("status")).toHaveText("Updates paused");
  await expect(
    page.getByRole("heading", { name: "Recent episodes" }),
  ).toBeVisible();
  const overflow = await page
    .locator(".training-shell")
    .evaluate((el) => el.scrollWidth > el.clientWidth);
  expect(overflow).toBe(false);
});

test("training dashboard desktop screenshot", async ({ page }) => {
  await page.route("**/api/training", (route) =>
    route.fulfill({ json: { run: fixture(), stale: false } }),
  );
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.goto("/training");
  await expect(page.getByRole("status")).toHaveText("Live training");
  await page.screenshot({ path: "test-results/training-dashboard.png" });
});
