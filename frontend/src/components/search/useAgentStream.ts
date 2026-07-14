import { useState, useCallback, useRef } from 'react';
import type { Paper } from './types';

export interface AgentStep {
  step: number;
  message: string;
  status: 'running' | 'success' | 'error';
  reasoning?: string;
  screenshot?: string;
}

export interface IngestionStats {
  totalPapers: number;
  successful: number;
  totalChunks: number;
}

export function useAgentStream() {
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [status, setStatus] = useState<'idle' | 'running' | 'done'>('idle');
  const [papers, setPapers] = useState<Paper[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [ingestionStats, setIngestionStats] = useState<IngestionStats | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const startSearch = useCallback(async (query: string) => {
    setSteps([]);
    setPapers([]);
    setError(null);
    setStatus('running');
    setIngestionStats(null);

    try {
      abortControllerRef.current = new AbortController();
      const response = await fetch(`http://localhost:8000/api/papers/search?q=${encodeURIComponent(query)}`, {
        signal: abortControllerRef.current.signal
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      if (!response.body) {
        throw new Error("No response body");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";
        
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const dataStr = line.substring(6);
            try {
              const data = JSON.parse(dataStr);
              
              if (data.type === "agent_step") {
                setSteps(prev => {
                  const existingStepIndex = prev.findIndex(s => s.step === data.step);
                  if (existingStepIndex >= 0) {
                    const newSteps = [...prev];
                    newSteps[existingStepIndex] = {
                      step: data.step,
                      message: data.message,
                      status: data.status,
                      reasoning: data.reasoning,
                      screenshot: data.screenshot || newSteps[existingStepIndex].screenshot
                    };
                    return newSteps;
                  } else {
                    return [...prev, {
                      step: data.step,
                      message: data.message,
                      status: data.status,
                      reasoning: data.reasoning,
                      screenshot: data.screenshot
                    }];
                  }
                });
              } else if (data.type === "final_result") {
                setPapers(data.papers);
                setStatus('done');
              } else if (data.type === "error") {
                setError(data.message);
                setStatus('done');
              } else if (data.type === "completed") {
                setStatus('done');
              }
            } catch (err) {
              console.error("Failed to parse SSE line:", err);
            }
          }
        }
      }
      
      // If the stream finished but we're still running (e.g. backend crashed and didn't send 'completed')
      setStatus(prev => {
        if (prev === 'running') return 'done';
        return prev;
      });

    } catch (err: any) {
      if (err.name === 'AbortError') {
        setStatus('idle');
        return;
      }
      setError(err.message || "An error occurred during search");
      setStatus('done');
    }
  }, []);

  const abortSearch = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setStatus('idle');
  }, []);

  const reset = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setSteps([]);
    setStatus('idle');
    setPapers([]);
    setError(null);
    setIngestionStats(null);
  }, []);

  return { steps, status, papers, error, ingestionStats, startSearch, abortSearch, reset };
}
