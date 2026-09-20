export type TrainingPreview = {
  episode: string;
  environment: number;
  captured_at: number;
  step: number;
  simulation_seconds: number;
  arena: number;
  goal: [number, number];
  goal_radius: number;
  obstacles: { x: number; y: number; radius: number; height: number }[];
  pose: { x: number; y: number; yaw: number };
  collision: boolean;
  trail: [number, number][];
};

export type TrainingSnapshot = {
  preview?: TrainingPreview;
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
  connectome?: {
    dataset: string;
    neurons: number;
    synapses: number;
    activity_semantics: "signed_tanh_hidden_state";
  };
  neural_activity?: {
    coordinate_status?: "available" | "unavailable" | "unsupported_dataset";
    captured_at: number;
    episode: string;
    step: number;
    semantics: "signed_tanh_hidden_state";
    neurons: {
      index: number;
      root_id: string;
      kind: "sensory" | "interneuron" | "descending";
      activation: number;
      magnitude: number;
      /** FlyWire v783 annotation anchor, transformed to atlas display space. */
      position?: [number, number, number];
    }[];
  };
};

export type TrainingResponse = { run: TrainingSnapshot | null; stale: boolean };
