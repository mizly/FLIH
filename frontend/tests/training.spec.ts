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
    connectome: {
      dataset: "FAFB v783",
      neurons: 139255,
      synapses: 3732460,
      activity_semantics: "signed_tanh_hidden_state",
    },
    neural_activity: {
      captured_at: Date.now() / 1000,
      episode: "2:7",
      step: 150,
      semantics: "signed_tanh_hidden_state",
      neurons: Array.from({ length: 96 }, (_, index) => ({
        index: 1200 + index,
        root_id: `7205759406000000${index.toString().padStart(2, "0")}`,
        kind:
          index % 17 === 0 ? ("descending" as const) : ("interneuron" as const),
        activation: (index % 2 ? -1 : 1) * (0.95 - index * 0.006),
        magnitude: 0.95 - index * 0.006,
      })),
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
  await expect(
    page.getByRole("img", { name: /bilateral FAFB fly-brain connectome/ }),
  ).toBeVisible();
  await expect(page.getByText("Last measured collection state")).toBeVisible();
  await expect(page.getByText("Strongest measured states")).toBeVisible();
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
  await expect(page.locator(".brain-viewport")).toHaveAttribute(
    "data-ready",
    "true",
  );
  await page.screenshot({ path: "test-results/training-dashboard.png" });
});

test("FAFB anatomy loads locally and rotates, zooms, and changes surface mode", async ({
  page,
}) => {
  await page.route("**/api/training", (route) =>
    route.fulfill({ json: { run: fixture(), stale: false } }),
  );
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/training");
  await expect(page.locator(".brain-viewport")).toHaveAttribute(
    "data-ready",
    "true",
  );
  const canvas = page.locator(".brain-viewport canvas");
  const pixels = () =>
    canvas.evaluate((el) => (el as HTMLCanvasElement).toDataURL());
  const front = await pixels();
  await page.getByRole("button", { name: "Side brain view" }).click();
  await expect.poll(pixels).not.toBe(front);
  await page.getByRole("button", { name: "Front brain view" }).click();
  await expect.poll(pixels).toBe(front);
  await canvas.focus();
  await page.keyboard.press("ArrowRight");
  await expect.poll(pixels).not.toBe(front);
  await page.keyboard.press("Home");
  await expect.poll(pixels).toBe(front);
  const box = (await canvas.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(
    box.x + box.width / 2 + 65,
    box.y + box.height / 2 + 25,
    { steps: 8 },
  );
  await page.mouse.up();
  await expect.poll(pixels).not.toBe(front);
  const rotated = await pixels();
  await page.getByRole("button", { name: "Zoom in on brain" }).click();
  await expect.poll(pixels).not.toBe(rotated);
  await page.getByRole("button", { name: "Front brain view" }).click();
  await page.getByRole("button", { name: "Surface", exact: true }).click();
  await expect.poll(pixels).not.toBe(front);
  await expect(
    page.getByRole("button", { name: "Surface", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page
    .locator(".training-brain")
    .screenshot({ path: "test-results/brain-surface.png" });
  await page.getByRole("button", { name: "Surface", exact: true }).click();
  await page
    .locator(".training-brain")
    .screenshot({ path: "test-results/brain-particles.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(canvas).toBeVisible();
  expect(
    await page
      .locator(".training-shell")
      .evaluate((el) => el.scrollWidth > el.clientWidth),
  ).toBe(false);
  expect(errors).toEqual([]);
});

test("brain atlas load failures show a useful fallback", async ({ page }) => {
  await page.route("**/api/training", (route) =>
    route.fulfill({ json: { run: fixture(), stale: false } }),
  );
  await page.route("**/brain/neuropils.json", (route) =>
    route.fulfill({ status: 503, body: "Unavailable" }),
  );
  await page.goto("/training");
  await expect(page.getByText(/Brain anatomy could not load/)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Front brain view" }),
  ).toBeDisabled();
});

test("sampled 3D preview updates, pauses, orbits and holds during optimization", async ({
  page,
}) => {
  let run = fixture();
  run.phase = "collecting";
  run.preview = {
    episode: "2:1",
    environment: 0,
    captured_at: Date.now() / 1000,
    step: 150,
    simulation_seconds: 3,
    arena: 7,
    goal: [4, 3],
    goal_radius: 0.35,
    pose: { x: -1, y: -2, yaw: 0.6 },
    collision: false,
    trail: [
      [-4, -3],
      [-3, -2.5],
      [-2, -2.4],
      [-1, -2],
    ],
    obstacles: [
      { x: 2, y: 1, radius: 0.4, height: 1.6 },
      { x: -3, y: 1, radius: 0.4, height: 1.6 },
      { x: 3, y: -3, radius: 0.4, height: 1.6 },
    ],
  };
  await page.route("**/api/training", (route) =>
    route.fulfill({ json: { run, stale: false } }),
  );
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.goto("/training");
  const scene = page.getByRole("img", { name: /3D training arena/ });
  await expect(scene).toBeVisible();
  await expect(
    page.getByText("Live · sampled view", { exact: true }),
  ).toBeVisible();
  const pixels = () =>
    scene.evaluate((el) => (el as HTMLCanvasElement).toDataURL());
  const original = await pixels();
  await page.getByRole("slider", { name: "Orbit camera" }).fill("1.2");
  await expect.poll(pixels).not.toBe(original);
  await page.getByRole("button", { name: "Pause preview" }).click();
  const paused = await pixels();
  run = {
    ...run,
    preview: {
      ...run.preview!,
      step: 250,
      captured_at: Date.now() / 1000,
      pose: { x: 3, y: 2, yaw: 1 },
    },
    environment_steps: 25000,
  };
  await expect(page.getByText("25,000", { exact: true })).toBeVisible();
  expect(await pixels()).toBe(paused);
  await expect(page.locator(".training-scene-readout")).toContainText(
    "STEP 150",
  );
  await page.getByRole("button", { name: "Resume preview" }).click();
  await expect(page.locator(".training-scene-readout")).toContainText(
    "STEP 250",
  );
  await expect.poll(pixels).not.toBe(paused);
  run = { ...run, phase: "optimizing" };
  await expect(
    page.getByText("Optimizing · holding last scene", { exact: true }),
  ).toBeVisible();
  await page.screenshot({ path: "test-results/training-3d-preview.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page
      .locator(".training-shell")
      .evaluate((el) => el.scrollWidth > el.clientWidth),
  ).toBe(false);
});
