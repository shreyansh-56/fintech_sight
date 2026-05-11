/** WebSocket hook for real-time progress updates */
import { useEffect, useRef, useState } from "react";

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export interface ProgressEvent {
  type: string;
  job_id: string;
  stage?: string;
  message?: string;
  progress?: number;
  error?: string;
  report_path?: string;
}

export function useWebSocket(jobId: string) {
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!jobId) return;

    const ws = new WebSocket(`${WS_BASE}/ws/${jobId}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data) as ProgressEvent;
      setEvents((prev) => [...prev, data]);
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };

    ws.onclose = () => {
      setIsConnected(false);
    };

    return () => {
      ws.close();
    };
  }, [jobId]);

  return { events, isConnected };
}
