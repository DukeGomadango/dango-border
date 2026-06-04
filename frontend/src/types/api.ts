export interface TierPrediction {
  p10: number;
  p50: number;
  p90: number;
  historical_mean?: number | null;
}

export interface PredictionStep {
  date: string;
  predictions: Record<string, TierPrediction>;
}

export interface DeepPredictionResponse {
  target_group: string;
  model_type: string;
  model_version: string;
  blending_status?: string;
  w_tft?: number;
  steps: PredictionStep[];
}

export interface JobProgress {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  stage: string;
  error?: string | null;
}

export interface PublicationPlan {
  goal: number;
  published_count: number;
  remaining_slots: number;
  ready_published: number;
  beta_published: number;
  beta_candidates_eligible: number;
  beta_candidates_total: number;
  updated_at: string;
}

export interface PublicationCandidate {
  target: string;
  status: string;
  publish: boolean;
  eligible: boolean;
  reasons: string[];
  has_active_model: boolean;
  adopted: boolean;
  improvement_rate: number | null;
  cv_mae: number | null;
}

export interface TargetOperationRow {
  target: string;
  status: "ready" | "beta" | "blocked";
  publish: boolean;
  coverage: number;
  missing_rate: number;
  valid_count: number;
  has_active_model: boolean;
  active_model_version: string | null;
  active_model_type: string | null;
  last_trained_at: string | null;
  last_adopted: boolean;
  cv_mae: number | null;
  baseline_mae: number | null;
  improvement_rate: number | null;
}

export interface TrainResult {
  target: string;
  adopted: boolean;
  model_version?: string;
  model_type?: string;
}

export interface TrainAllData {
  results: TrainResult[];
  errors: { target: string; error: string }[];
  detail?: string;
}

export interface UploadData {
  job_id?: string;
  detail?: string;
}
