export type TrainingSnapshot = {
  schema_version: number;
  run_id: string;
  started_at: number;
  updated_at: number;
  elapsed_seconds: number;
  status: "running" | "completed" | "interrupted" | "failed";
  phase: string;
  iteration: number;
  episodes_in_iteration: number;
  train_step: number;
  environment_steps: number;
  episodes_total: number;
  successes: number;
  collision_episodes: number;
  beta?: number;
  error: string | null;
  config: {
    model: string;
    iterations: number;
    episodes_per_iteration: number;
    train_steps: number;
    environments: number;
    learning_rate: number;
    batch_size: number;
    max_episode_steps: number;
    lidar_rays: number;
    lidar_rate_hz: number;
    camera_size: number[];
  };
  loss_history: { step: number; iteration: number; loss: number | null }[];
  episodes: {
    episode: number;
    iteration: number;
    reward: number;
    steps: number;
    success: boolean;
    collision: boolean;
    distance: number;
  }[];
  iterations: {
    iteration: number;
    mean_loss: number | null;
    batches: number;
  }[];
  checkpoints: { name: string; iteration: number; saved_at: number }[];
  buffer_counts: Record<string, number>;
};

export type TrainingResponse = { run: TrainingSnapshot | null; stale: boolean };
