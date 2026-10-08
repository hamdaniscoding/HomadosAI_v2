export type Reason = 
  | 'detector_busy'
  | 'thresholds_not_calibrated'
  | 'window_too_short'
  | 'audio_too_quiet'
  | 'audio_too_noisy';

export interface WsReadyMessage {
  type: 'ready';
  session_id: string;
  window_seconds: number;
  hop_seconds: number;
  detector: string | null;
}

export interface WsStatusMessage {
  type: 'status';
  received_seconds: number;
  speech_seconds: number;
  needed_seconds: number;
}

export interface WsResultMessage {
  type: 'result';
  seq: number;
  t: number;
  window_seconds: number;
  ai_probability: number | null;
  smoothed_probability: number | null;
  verdict: string | null;
  latency_ms: number | null;
  detector: string | null;
  speech_ratio: number;
  reason: Reason | null | string;
  active_speaker: string | null;
  speakers: Array<{
    id: string;
    speech_seconds: number;
    ai_probability: number | null;
    smoothed_probability: number | null;
    reason: Reason | null | string;
  }>;
}

export interface WsErrorMessage {
  type: 'error';
  code: string;
  message: string;
}

export type ServerMessage = WsReadyMessage | WsStatusMessage | WsResultMessage | WsErrorMessage;
