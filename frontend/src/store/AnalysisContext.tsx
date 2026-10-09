import { createContext, useContext, useState, ReactNode } from 'react';
import { StreamState } from '../lib/stream';
import { WsResultMessage, WsStatusMessage } from '../types/protocol';

interface AnalysisState {
  state: StreamState;
  sourceName: string;
  sessionId: string;
  scores: WsResultMessage[];
  latestScore: WsResultMessage | null;
  latestStatus: WsStatusMessage | null;
  fileProgress: { received: number; total: number } | null;
  errorMsg: string;
  rms: number;
  deviceName: string;
  
  setState: (s: StreamState) => void;
  setSourceName: (n: string) => void;
  setSessionId: (id: string) => void;
  setScores: (scores: WsResultMessage[] | ((prev: WsResultMessage[]) => WsResultMessage[])) => void;
  setLatestScore: (score: WsResultMessage | null) => void;
  setLatestStatus: (status: WsStatusMessage | null) => void;
  setFileProgress: (progress: { received: number; total: number } | null) => void;
  setErrorMsg: (msg: string) => void;
  setRms: (rms: number) => void;
  setDeviceName: (name: string) => void;
  reset: () => void;
}

const AnalysisContext = createContext<AnalysisState | undefined>(undefined);

export const AnalysisProvider = ({ children }: { children: ReactNode }) => {
  const [state, setState] = useState<StreamState>('idle');
  const [sourceName, setSourceName] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [scores, setScores] = useState<WsResultMessage[]>([]);
  const [latestScore, setLatestScore] = useState<WsResultMessage | null>(null);
  const [latestStatus, setLatestStatus] = useState<WsStatusMessage | null>(null);
  const [fileProgress, setFileProgress] = useState<{ received: number; total: number } | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [rms, setRms] = useState(0);
  const [deviceName, setDeviceName] = useState('');

  const reset = () => {
    setState('idle');
    setSourceName('');
    setSessionId('');
    setScores([]);
    setLatestScore(null);
    setLatestStatus(null);
    setFileProgress(null);
    setErrorMsg('');
    setRms(0);
    setDeviceName('');
  };

  return (
    <AnalysisContext.Provider value={{
      state, sourceName, sessionId, scores, latestScore, latestStatus, fileProgress, errorMsg, rms, deviceName,
      setState, setSourceName, setSessionId, setScores, setLatestScore, setLatestStatus, setFileProgress, setErrorMsg, setRms, setDeviceName, reset
    }}>
      {children}
    </AnalysisContext.Provider>
  );
};

export const useAnalysis = () => {
  const context = useContext(AnalysisContext);
  if (context === undefined) {
    throw new Error('useAnalysis must be used within an AnalysisProvider');
  }
  return context;
};
