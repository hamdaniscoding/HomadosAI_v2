import { ServerMessage } from '../types/protocol';

export type StreamState = 'idle' | 'requesting' | 'connecting' | 'collecting' | 'live' | 'stopping' | 'stopped' | 'reconnecting' | 'error';

export interface StreamCallbacks {
  onStateChange: (state: StreamState) => void;
  onMessage: (msg: ServerMessage) => void;
  onError: (msg: string) => void;
  onProgress?: (received: number, total: number) => void;
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

  public async startFile(file: File, save: boolean) {
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
            this.stop();
          }
        }, 50);
      });
      
    } catch (e) {
      this.callbacks.onError('Unsupported or corrupt file');
      this.setState('error');
    }
  }
  
  public stop() {
    this.setState('stopping');
    if (this.fileSimTimer) {
      clearInterval(this.fileSimTimer);
      this.fileSimTimer = null;
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
    this.setState('stopped');
  }
}
