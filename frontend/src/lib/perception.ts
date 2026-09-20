export type OmniReading = {
  obstacle_ahead?: boolean;
  obstacle_distance_m?: number | null;
  obstacle_summary?: string;
  summary?: string;
  confidence?: number;
  reasoning?: string;
  error?: string;
  updated_at?: number;
};
