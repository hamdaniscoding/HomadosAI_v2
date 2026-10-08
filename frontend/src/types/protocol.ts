export type Reason = 
  | 'detector_busy'
  | 'thresholds_not_calibrated'
  | 'window_too_short'
  | 'audio_too_quiet'
  | 'audio_too_noisy';

export interface ScoreUpdate {
  type: 'score';
  t: number;
  ai_probability: number | null;
  smoothed_probability: number | null;
  reason: Reason | null | string;
  speakers?: Array<{
    id: string;
    speech_seconds: number;
    ai_probability: number | null;
    smoothed_probability: number | null;
    reason: Reason | null | string;
  }>;
  active_speaker?: string | null;
  received_seconds: number;
  needed_seconds: number;
  detector_name: string;
  latency_ms: number;
  speech_ratio: number;
  session_id: string;
}

export interface ServerError {
  type: 'error';
  code: string;
  message: string;
}

export type ServerMessage = ScoreUpdate | ServerError;
