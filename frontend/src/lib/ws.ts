"use client";

import { useEffect, useRef, useState } from "react";

import { config } from "@/lib/config";
import type { AlertCreatedEvent, MetricsTick, WsEnvelope } from "@/lib/types";

export type LiveStatus = "connecting" | "live" | "offline";

/**
 * Shared resilient WebSocket subscription. Reconnects with capped backoff and
 * invokes `onMessage` for every frame whose `topic` matches.
 */
function useLiveTopic<T extends { topic: string }>(
  path: "/ws/alerts" | "/ws/metrics",
  topic: string,
  token: string | null,
  onMessage: (event: T) => void,
): LiveStatus {
  const [status, setStatus] = useState<LiveStatus>("offline");
  const handlerRef = useRef(onMessage);
  handlerRef.current = onMessage;

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
      socket = new WebSocket(config.wsUrl(path, token));
      socket.onopen = () => {
        attempt = 0;
        setStatus("live");
      };
      socket.onmessage = (message) => {
        try {
          const envelope = JSON.parse(message.data as string) as WsEnvelope;
          if (envelope.topic === topic) handlerRef.current(envelope as unknown as T);
        } catch {
          /* ignore malformed frames */
        }
      };
      socket.onclose = () => {
        if (closed) return;
        setStatus("offline");
        attempt += 1;
        reconnectTimer = setTimeout(connect, Math.min(1000 * 2 ** attempt, 15000));
      };
      socket.onerror = () => socket?.close();
    };

    connect();
    return () => {
      closed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [path, topic, token]);

  return status;
}

export function useLiveAlerts(
  token: string | null,
  onAlert: (event: AlertCreatedEvent) => void,
): { status: LiveStatus } {
  const status = useLiveTopic<AlertCreatedEvent>("/ws/alerts", "alert.created", token, onAlert);
  return { status };
}

export function useLiveMetrics(
  token: string | null,
  onTick: (event: MetricsTick) => void,
): { status: LiveStatus } {
  const status = useLiveTopic<MetricsTick>("/ws/metrics", "metrics.tick", token, onTick);
  return { status };
}
