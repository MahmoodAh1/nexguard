"use client";

import { useEffect, useRef, useState } from "react";

import { config } from "@/lib/config";
import type { AlertCreatedEvent, WsEnvelope } from "@/lib/types";

export type LiveStatus = "connecting" | "live" | "offline";

interface UseLiveAlertsResult {
  status: LiveStatus;
}

/**
 * Maintains a resilient WebSocket to the alert stream. Reconnects with capped
 * backoff, and invokes `onAlert` for every `alert.created` event so callers can
 * update their cache / prepend the row in real time.
 */
export function useLiveAlerts(
  token: string | null,
  onAlert: (event: AlertCreatedEvent) => void,
): UseLiveAlertsResult {
  const [status, setStatus] = useState<LiveStatus>("offline");
  const onAlertRef = useRef(onAlert);
  onAlertRef.current = onAlert;

  useEffect(() => {
    if (!token) {
      setStatus("offline");
      return;
    }

    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;
    let closed = false;

    const connect = () => {
      setStatus("connecting");
      socket = new WebSocket(config.wsUrl(token));

      socket.onopen = () => {
        attempt = 0;
        setStatus("live");
      };

      socket.onmessage = (message) => {
        try {
          const envelope = JSON.parse(message.data as string) as WsEnvelope;
          if (envelope.topic === "alert.created") {
            onAlertRef.current(envelope as unknown as AlertCreatedEvent);
          }
        } catch {
          // Ignore malformed frames.
        }
      };

      socket.onclose = () => {
        if (closed) return;
        setStatus("offline");
        attempt += 1;
        const delay = Math.min(1000 * 2 ** attempt, 15000);
        reconnectTimer = setTimeout(connect, delay);
      };

      socket.onerror = () => socket?.close();
    };

    connect();

    return () => {
      closed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [token]);

  return { status };
}
