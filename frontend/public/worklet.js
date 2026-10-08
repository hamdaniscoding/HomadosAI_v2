class AudioCaptureWorklet extends AudioWorkletProcessor {
  constructor() {
    super();
    this.bufferSize = 1600; // 100ms at 16kHz
    this.buffer = new Float32Array(this.bufferSize);
    this.offset = 0;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || input.length === 0 || !input[0]) return true;

    // Downmix to mono if needed
    const channelData = input[0]; 

    for (let i = 0; i < channelData.length; i++) {
      this.buffer[this.offset++] = channelData[i];
      if (this.offset >= this.bufferSize) {
        // convert to int16
        const int16Buffer = new Int16Array(this.bufferSize);
        for (let j = 0; j < this.bufferSize; j++) {
          let s = Math.max(-1, Math.min(1, this.buffer[j]));
          int16Buffer[j] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        
        // post to main thread
        this.port.postMessage(int16Buffer.buffer, [int16Buffer.buffer]);
        this.offset = 0;
      }
    }
    return true;
  }
}

registerProcessor('audio-capture-worklet', AudioCaptureWorklet);
