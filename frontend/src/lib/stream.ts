import { ServerMessage } from '../types/protocol';

export type StreamState =
  | 'idle'
  | 'requesting'
  | 'connecting'
  | 'collecting'
  | 'live'
  | 'stopping'
  | 'stopped'
  | 'reconnecting'
  | 'error'
  | 'finished'
  | 'failed'
  | 'analyzing';

export interface StreamCallbacks {
  onStateChange: (state: StreamState) => void;
  onMessage: (msg: ServerMessage) => void;
  onError: (msg: string) => void;
  onProgress?: (received: number, total: number) => void;
  onRms?: (rms: number) => void;
  onDeviceName?: (name: string) => void;
}

export class AudioStreamClient {
  private ws: WebSocket | null = null;
  private audioCtx: AudioContext | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private worklet: AudioWorkletNode | null = null;
  private mediaStream: MediaStream | null = null;
  private reconnectTries = 0;
  private maxTries = 5;
  private saveSession = false;
  private sourceName = 'Microphone';
  public deviceName = '';
  private isUserStopped = false;
  private fileSimTimer: ReturnType<typeof setInterval> | null = null;
  private pollTimer: ReturnType<typeof setTimeout> | null = null;
  private abortController: AbortController | null = null;

  constructor(private callbacks: StreamCallbacks) {}

  private setState(s: StreamState) {
    this.callbacks.onStateChange(s);
  }

  private connectWS(onOpen?: () => void) {
    const wsUrl =
      (window.location.protocol === 'https:' ? 'wss:' : 'ws:') +
      '//' +
      (import.meta.env.DEV ? '127.0.0.1:8000' : window.location.host) +
      '/api/v1/ws/stream';
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.reconnectTries = 0;
      this.ws?.send(
        JSON.stringify({
          type: 'start',
          sample_rate: 16000,
          channels: 1,
          encoding: 'pcm_s16le',
          mode: 'single',
          source_name: this.sourceName,
          save_session: this.saveSession,
        })
      );
      if (onOpen) onOpen();
    };

    this.ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data) as ServerMessage;
        this.callbacks.onMessage(msg);
      } catch (err) {
        console.error('Failed to parse WebSocket message', e.data);
      }
    };

    this.ws.onclose = () => {
      if (this.isUserStopped) {
        return;
      }
      if (this.reconnectTries < this.maxTries) {
        this.setState('reconnecting');
        const delay = Math.min(10000, Math.pow(2, this.reconnectTries) * 1000);
        setTimeout(() => {
          if (!this.isUserStopped) {
            this.connectWS();
          }
        }, delay);
        this.reconnectTries++;
      } else {
        this.callbacks.onError('Connection to detection server lost.');
        this.stop(false);
        this.setState('failed');
      }
    };

    this.ws.onerror = () => {
      // Handled by onclose
    };
  }

  private async setupAudioCapture(stream: MediaStream) {
    const AudioContextClass =
      window.AudioContext || (window as any).webkitAudioContext;
    this.audioCtx = new AudioContextClass({ sampleRate: 16000 });

    const base = import.meta.env.BASE_URL || '/';
    const workletUrl = `${base.replace(/\/$/, '')}/worklet.js`;

    try {
      await this.audioCtx.audioWorklet.addModule(workletUrl);
    } catch (e: any) {
      console.error('Failed to load AudioWorklet module:', e);
      this.callbacks.onError(`Failed to load audio worklet processor: ${e.message || e}`);
      this.stop(false);
      this.setState('failed');
      return;
    }

    if (this.audioCtx.state === 'suspended') {
      try {
        await this.audioCtx.resume();
      } catch (e) {
        console.warn('AudioContext resume error:', e);
      }
    }

    this.source = this.audioCtx.createMediaStreamSource(stream);
    this.worklet = new AudioWorkletNode(this.audioCtx, 'audio-capture-worklet');

    this.worklet.port.onmessage = (e) => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        if (this.ws.bufferedAmount > 1024 * 1024) {
          this.callbacks.onError('Audio streaming backlog exceeded 1MB.');
          this.stop(false);
          this.setState('failed');
          return;
        }
        this.ws.send(e.data);

        if (this.callbacks.onRms) {
          const int16 = new Int16Array(e.data);
          let sum = 0;
          for (let i = 0; i < int16.length; i++) {
            const val = int16[i] / 32768;
            sum += val * val;
          }
          const rms = Math.sqrt(sum / int16.length);
          this.callbacks.onRms(rms);
        }
      }
    };

    this.source.connect(this.worklet);
    this.worklet.connect(this.audioCtx.destination);
    this.setState('collecting');
  }

  public async startMicrophone(save: boolean) {
    this.saveSession = save;
    this.sourceName = 'Microphone';
    this.isUserStopped = false;
    this.setState('requesting');

    try {
      // Explicit constraints for speech anti-spoofing detection:
      // - channelCount: 1 (single-channel mono prevents spatial mixing / phase anomalies)
      // - echoCancellation: false (AEC applies non-linear adaptive filters distorting phase & vocal tract cues)
      // - noiseSuppression: false (spectral subtractive denoisers remove fine human harmonics and breath cues)
      // - autoGainControl: false (AGC dynamically modifies audio volume envelope, skewing spectral energy)
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      });

      const audioTrack = this.mediaStream.getAudioTracks()[0];
      if (audioTrack) {
        this.deviceName = audioTrack.label || 'Default Microphone';
        this.callbacks.onDeviceName?.(this.deviceName);
        audioTrack.onended = () => {
          if (!this.isUserStopped) {
            this.callbacks.onError('Microphone disconnected or permission was revoked.');
            this.stop(false);
            this.setState('failed');
          }
        };
      }

      this.setState('connecting');
      this.connectWS(() => this.setupAudioCapture(this.mediaStream!));
    } catch (e: any) {
      let friendlyError = 'Failed to access microphone.';
      if (e.name === 'NotAllowedError' || e.name === 'PermissionDeniedError') {
        friendlyError =
          'Microphone permission was denied. Please allow microphone access in your browser site settings. (If using Brave, relax Brave Shields for 127.0.0.1 / localhost).';
      } else if (e.name === 'NotFoundError' || e.name === 'DevicesNotFoundError') {
        friendlyError =
          'No microphone device was detected. Please connect a working audio input device.';
      } else if (e.name === 'NotReadableError' || e.name === 'TrackStartError') {
        friendlyError =
          'Microphone is currently in use by another application or the operating system cannot access it.';
      } else if (e.name === 'SecurityError') {
        friendlyError =
          'Microphone capture requires a secure context (HTTPS or http://127.0.0.1 / http://localhost).';
      } else if (e.message) {
        friendlyError = `Microphone error: ${e.message}`;
      }

      this.callbacks.onError(friendlyError);
      this.setState('failed');
    }
  }

  public async startTab(save: boolean) {
    this.saveSession = save;
    this.sourceName = 'Tab Audio';
    this.isUserStopped = false;
    this.setState('requesting');
    try {
      this.mediaStream = await navigator.mediaDevices.getDisplayMedia({
        audio: true,
        video: true,
      });
      const videoTracks = this.mediaStream.getVideoTracks();
      videoTracks.forEach((t) => t.stop());

      const audioTracks = this.mediaStream.getAudioTracks();
      if (audioTracks.length === 0) {
        this.callbacks.onError('No audio stream found in selected screen/tab.');
        this.setState('failed');
        return;
      }

      this.deviceName = audioTracks[0].label || 'Tab Audio';
      this.callbacks.onDeviceName?.(this.deviceName);
      audioTracks[0].onended = () => {
        if (!this.isUserStopped) {
          this.stop(true);
        }
      };

      this.setState('connecting');
      this.connectWS(() => this.setupAudioCapture(this.mediaStream!));
    } catch (e: any) {
      this.callbacks.onError('Tab share cancelled or not supported.');
      this.setState('failed');
    }
  }

  public async startFileSimulated(file: File, save: boolean) {
    this.saveSession = save;
    this.sourceName = file.name + ' (Replay)';
    this.isUserStopped = false;
    this.setState('requesting');

    try {
      const buffer = await file.arrayBuffer();
      const ctx = new OfflineAudioContext(1, 1, 16000);
      const audioBuffer = await ctx.decodeAudioData(buffer);

      const resampledCtx = new OfflineAudioContext(
        1,
        Math.max(1, Math.floor(audioBuffer.duration * 16000)),
        16000
      );
      const source = resampledCtx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(resampledCtx.destination);
      source.start();

      const renderedBuffer = await resampledCtx.startRendering();
      const pcmFloat = renderedBuffer.getChannelData(0);

      this.setState('connecting');
      this.connectWS(() => {
        this.setState('collecting');

        let offset = 0;
        const chunkSize = 1600; // 100ms
        const startTime = performance.now();

        this.fileSimTimer = setInterval(() => {
          if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

          const now = performance.now();
          const elapsed = (now - startTime) / 1000;
          const targetOffset = Math.floor(elapsed * 16000);

          while (offset < targetOffset && offset < pcmFloat.length) {
            const end = Math.min(offset + chunkSize, pcmFloat.length);
            const chunk = pcmFloat.subarray(offset, end);

            const int16 = new Int16Array(chunk.length);
            let sum = 0;
            for (let i = 0; i < chunk.length; i++) {
              const s = Math.max(-1, Math.min(1, chunk[i]));
              int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
              sum += s * s;
            }

            this.ws.send(int16.buffer);
            offset += chunk.length;

            if (this.callbacks.onRms) {
              this.callbacks.onRms(Math.sqrt(sum / chunk.length));
            }
          }

          if (this.callbacks.onProgress) {
            this.callbacks.onProgress(offset / 16000, pcmFloat.length / 16000);
          }

          if (offset >= pcmFloat.length) {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
              this.ws.send(JSON.stringify({ type: 'stop' }));
            }
            if (this.fileSimTimer) {
              clearInterval(this.fileSimTimer);
              this.fileSimTimer = null;
            }
          }
        }, 50);
      });
    } catch (e: any) {
      this.callbacks.onError('Unsupported or corrupted audio file.');
      this.setState('failed');
    }
  }

  public async startFileUpload(file: File, save: boolean) {
    this.saveSession = save;
    this.sourceName = file.name;
    this.isUserStopped = false;
    this.setState('requesting');

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('save_session', save ? 'true' : 'false');

      const baseUrl = import.meta.env.DEV ? 'http://127.0.0.1:8000' : '';
      const response = await fetch(`${baseUrl}/api/v1/analyze`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed with status ${response.status}`);
      }

      const data = await response.json();
      const jobId = data.job_id;

      this.setState('collecting');

      let since = 0;
      let consecutiveFailures = 0;
      this.abortController = new AbortController();

      const poll = async () => {
        try {
          const res = await fetch(`${baseUrl}/api/v1/jobs/${jobId}?since=${since}`, {
            signal: this.abortController?.signal,
          });
          if (!res.ok) throw new Error(`Poll failed: ${res.status}`);
          const jobData = await res.json();
          consecutiveFailures = 0;

          if (jobData.results && jobData.results.length > 0) {
            for (const result of jobData.results) {
              this.callbacks.onMessage({ type: 'result', ...result } as any);
            }
            since = jobData.results[jobData.results.length - 1].seq;
          }

          if (jobData.status === 'done' || jobData.status === 'error') {
            if (this.pollTimer) {
              clearTimeout(this.pollTimer);
              this.pollTimer = null;
            }
            if (jobData.status === 'error') {
              this.callbacks.onError(jobData.error || 'Analysis job encountered an error');
              this.setState('failed');
            } else {
              this.setState('finished');
            }
            return;
          }

          this.pollTimer = setTimeout(poll, 500);
        } catch (e: any) {
          if (e.name === 'AbortError') return;
          consecutiveFailures++;
          if (consecutiveFailures >= 5) {
            this.callbacks.onError(e.message || 'Job polling failed repeatedly');
            this.setState('failed');
            return;
          }
          this.pollTimer = setTimeout(poll, 1500);
        }
      };

      poll();
    } catch (e: any) {
      this.callbacks.onError(e.message || 'Upload failed');
      this.setState('failed');
    }
  }

  public stop(markFinished: boolean = true) {
    this.isUserStopped = true;
    this.setState('stopping');

    if (this.fileSimTimer) {
      clearInterval(this.fileSimTimer);
      this.fileSimTimer = null;
    }
    if (this.pollTimer) {
      clearTimeout(this.pollTimer);
      this.pollTimer = null;
    }
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }

    if (this.ws) {
      if (this.ws.readyState === WebSocket.OPEN) {
        try {
          this.ws.send(JSON.stringify({ type: 'stop' }));
        } catch (e) {
          // ignore
        }
      }
      this.ws.onclose = null;
      this.ws.close();
      this.ws = null;
    }

    if (this.worklet) {
      try {
        this.worklet.disconnect();
      } catch (e) {}
      this.worklet = null;
    }
    if (this.source) {
      try {
        this.source.disconnect();
      } catch (e) {}
      this.source = null;
    }
    if (this.audioCtx) {
      try {
        this.audioCtx.close();
      } catch (e) {}
      this.audioCtx = null;
    }
    if (this.mediaStream) {
      try {
        this.mediaStream.getTracks().forEach((t) => t.stop());
      } catch (e) {}
      this.mediaStream = null;
    }

    if (markFinished) {
      this.setState('finished');
    }
  }
}
