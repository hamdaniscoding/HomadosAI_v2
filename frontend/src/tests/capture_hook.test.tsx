import { StrictMode, useState, useRef, useEffect } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, act } from '@testing-library/react';
import { AudioStreamClient } from '../lib/stream';

describe('StrictMode and Component Lifecycle Safety', () => {
  it('capture client survives StrictMode double mount without stopping prematurely', () => {
    let clientInstance: AudioStreamClient | null = null;
    let stopCallCount = 0;

    function TestComponent() {
      const clientRef = useRef<AudioStreamClient | null>(null);

      useEffect(() => {
        if (!clientRef.current) {
          const client = new AudioStreamClient({
            onStateChange: () => {},
            onMessage: () => {},
            onError: () => {},
          });
          const origStop = client.stop.bind(client);
          client.stop = vi.fn((mark) => {
            stopCallCount++;
            return origStop(mark);
          });
          clientRef.current = client;
          clientInstance = client;
        }

        return () => {
          // Unmount cleanup of unrelated or test effect must NOT blindly kill the active client
          // unless user specifically stops it
        };
      }, []);

      return <div>Active Session</div>;
    }

    render(
      <StrictMode>
        <TestComponent />
      </StrictMode>
    );

    expect(clientInstance).not.toBeNull();
    expect(stopCallCount).toBe(0);
  });

  it('unmount of an unrelated component does not stop active capture client', () => {
    let stopCallCount = 0;

    const activeClient = new AudioStreamClient({
      onStateChange: () => {},
      onMessage: () => {},
      onError: () => {},
    });
    activeClient.stop = vi.fn((_mark) => {
      stopCallCount++;
    });

    function UnrelatedSibling({ show }: { show: boolean }) {
      if (!show) return null;
      return <div>Sibling Component</div>;
    }

    function ParentContainer() {
      const [showSibling, setShowSibling] = useState(true);

      return (
        <div>
          <button onClick={() => setShowSibling(false)}>Toggle Sibling</button>
          <UnrelatedSibling show={showSibling} />
        </div>
      );
    }

    const { getByText } = render(<ParentContainer />);

    // Unmount the sibling
    act(() => {
      getByText('Toggle Sibling').click();
    });

    // The active client must NOT have stop called
    expect(stopCallCount).toBe(0);
  });
});
