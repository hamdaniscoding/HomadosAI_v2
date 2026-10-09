import { ServerMessage } from '../types/protocol';

export type StreamState = 'idle' | 'requesting' | 'connecting' | 'collecting' | 'live' | 'stopping' | 'stopped' | 'reconnecting' | 'error' | 'finished' | 'failed' | 'analyzing';

export interface StreamCallbacks {
  onStateChange: (state: StreamState) => void;
  onMessage: (msg: ServerMessage) => void;
  onError: (msg: string) => void;
  onProgress?: (received: number, total: number) => void;
  onRms?: (rms: number) => void;
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
  private fileSimTimer: ReturnType<typeof setInterval> | null = null;
  
  constructor(private callbacks: StreamCallbacks) {}
  
  private setState(s: StreamState) {
    this.callbacks.onStateChange(s);
  }
  
  private connectWS(onOpen: () => void) {
    const wsUrl = (window.location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + (import.meta.env.DEV ? '127.0.0.1:8000' : window.location.host) + '/api/v1/ws/stream';
    this.ws = new WebSocket(wsUrl);
    
    this.ws.onopen = () => {
      this.reconnectTries = 0;
      this.ws?.send(JSON.stringify({
        type: 'start',
        sample_rate: 16000,
        channels: 1,
        encoding: 'pcm_s16le',
        mode: 'single',
        save_session: this.saveSession
      }));
      onOpen();
    };
    
    this.ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data) as ServerMessage;
        this.callbacks.onMessage(msg);
      } catch (err) {
        console.error('Failed to parse message', e.data);
      }
    };
    
    this.ws.onclose = () => {
      if (this.reconnectTries < this.maxTries) {
        this.setState('reconnecting');
        setTimeout(() => this.connectWS(onOpen), Math.pow(2, this.reconnectTries) * 1000);
        this.reconnectTries++;
      } else {
        this.callbacks.onError('WebSocket disconnected');
        this.stop();
      }
    };
    
    this.ws.onerror = () => {
      // ws.onclose handles retry logic
    };
  }

  private async setupAudioCapture(stream: MediaStream) {
    this.audioCtx = new AudioContext({ sampleRate: 16000 });
    await this.audioCtx.audioWorklet.addModule('/worklet.js');
    
    this.source = this.audioCtx.createMediaStreamSource(stream);
    this.worklet = new AudioWorkletNode(this.audioCtx, 'audio-capture-worklet');
    
    this.worklet.port.onmessage = (e) => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        if (this.ws.bufferedAmount > 1024 * 1024) {
          // connection too slow
          this.callbacks.onError('Connection too slow');
          this.stop();
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
          this.callbacks.onRms(Math.sqrt(sum / int16.length));
        }
      }
    };
    
    this.source.connect(this.worklet);
    this.worklet.connect(this.audioCtx.destination);
    this.setState('collecting');
  }

  public async startMicrophone(save: boolean) {
    this.saveSession = save;
    this.setState('requesting');
    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({ 
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false } 
      });
      this.setState('connecting');
      this.connectWS(() => this.setupAudioCapture(this.mediaStream!));
    } catch (e) {
      this.callbacks.onError('Microphone permission denied');
      this.setState('error');
    }
  }
  
  public async startTab(save: boolean) {
    this.saveSession = save;
    this.setState('requesting');
    try {
      this.mediaStream = await navigator.mediaDevices.getDisplayMedia({ audio: true, video: true });
      const videoTracks = this.mediaStream.getVideoTracks();
      videoTracks.forEach(t => t.stop());
      
      const audioTracks = this.mediaStream.getAudioTracks();
      if (audioTracks.length === 0) {
        this.callbacks.onError('Tab share without audio');
        this.setState('error');
        return;
      }
      
      this.setState('connecting');
      this.connectWS(() => this.setupAudioCapture(this.mediaStream!));
      
      audioTracks[0].onended = () => this.stop();
      
    } catch (e) {
      this.callbacks.onError('Tab share cancelled');
      this.setState('error');
    }
  }

  public async startFileSimulated(file: File, save: boolean) {
    this.saveSession = save;
    this.setState('requesting');
    
    try {
      const buffer = await file.arrayBuffer();
      const ctx = new OfflineAudioContext(1, 1, 16000);
      const audioBuffer = await ctx.decodeAudioData(buffer);
      
      const resampledCtx = new OfflineAudioContext(1, audioBuffer.duration * 16000, 16000);
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
        
        let startTime = performance.now();
        
        this.fileSimTimer = setInterval(() => {
          if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
          
          const now = performance.now();
          const elapsed = (now - startTime) / 1000;
          const targetOffset = Math.floor(elapsed * 16000);
          
          while (offset < targetOffset && offset < pcmFloat.length) {
            const end = Math.min(offset + chunkSize, pcmFloat.length);
            const chunk = pcmFloat.subarray(offset, end);
            
            const int16 = new Int16Array(chunk.length);
            for (let i = 0; i < chunk.length; i++) {
              let s = Math.max(-1, Math.min(1, chunk[i]));
              int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }
            
            this.ws.send(int16.buffer);
            offset += chunk.length;
          }
          
          if (this.callbacks.onProgress) {
            this.callbacks.onProgress(offset / 16000, pcmFloat.length / 16000);
          }
          
          if (offset >= pcmFloat.length) {
            this.ws.send(JSON.stringify({ type: 'stop' }));
            if (this.fileSimTimer) {
              clearInterval(this.fileSimTimer);
              this.fileSimTimer = null;
            }
          }
        }, 50);
      });
      
    } catch (e) {
      this.callbacks.onError('Unsupported or corrupt file');
      this.setState('failed');
    }
  }

  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private abortController: AbortController | null = null;

  public async startFileUpload(file: File, save: boolean) {
    this.saveSession = save;
    this.setState('requesting');
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('save_session', save ? 'true' : 'false');
      
      const baseUrl = import.meta.env.DEV ? 'http://127.0.0.1:8000' : '';
      const response = await fetch(`${baseUrl}/api/v1/analyze`, {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        throw new Error('Upload failed');
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
            signal: this.abortController?.signal
          });
          if (!res.ok) throw new Error(`Poll failed: ${res.status}`);
          const jobData = await res.json();
          console.log('POLL JOBDATA', jobData.status);
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
              this.callbacks.onError(jobData.error || 'Job failed');
              this.setState('failed');
            } else {
              this.setState('finished');
            }
            return;
          }
          
          this.pollTimer = setTimeout(poll, 500);
        } catch (e: any) {
          console.error('POLL EXCEPTION', e);
          if (e.name === 'AbortError') return;
          consecutiveFailures++;
          if (consecutiveFailures >= 5) {
            this.callbacks.onError(e.message || 'Polling failed');
            this.setState('failed');
            return;
          }
          this.pollTimer = setTimeout(poll, 1500);
        }
      };
      
      poll();
      
    } catch (e) {
      this.callbacks.onError('Upload failed');
      this.setState('failed');
    }
  }
  
  public stop() {
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
      this.ws.onclose = null;
      this.ws.close();
      this.ws = null;
    }
    if (this.worklet) {
      this.worklet.disconnect();
      this.worklet = null;
    }
    if (this.source) {
      this.source.disconnect();
      this.source = null;
    }
    if (this.audioCtx) {
      this.audioCtx.close();
      this.audioCtx = null;
    }
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(t => t.stop());
      this.mediaStream = null;
    }
    this.setState('finished');
  }
}
