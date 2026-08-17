"use client";

import { useEffect, useRef, useState } from "react";
import { wsUrl } from "@/lib/api";

export type WsMessage = { event: string; payload?: Record<string, unknown> } & Record<string, unknown>;

type Handlers = {
  onMessage?: (msg: WsMessage) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onReconnect?: () => void;
};

const MAX_BACKOFF_MS = 30_000;
const INITIAL_BACKOFF_MS = 1_000;

export function useMarketWebSocket(handlers: Handlers) {
  const [connected, setConnected] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    let unmounted = false;
    let attempt = 0;
    let openedOnce = false;

    function scheduleReconnect() {
      if (unmounted) return;
      setReconnecting(true);
      const delay = Math.min(MAX_BACKOFF_MS, INITIAL_BACKOFF_MS * 2 ** attempt);
      attempt += 1;
      retry = setTimeout(connect, delay);
    }

    function connect() {
      if (unmounted) return;
      try {
        ws = new WebSocket(wsUrl());
        ws.onopen = () => {
          if (unmounted) return;
          attempt = 0;
          setConnected(true);
          setReconnecting(false);
          handlersRef.current.onOpen?.();
          if (openedOnce) {
            handlersRef.current.onReconnect?.();
          }
          openedOnce = true;
        };
        ws.onclose = () => {
          if (unmounted) return;
          setConnected(false);
          handlersRef.current.onClose?.();
          scheduleReconnect();
        };
        ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data) as WsMessage;
            handlersRef.current.onMessage?.(msg);
          } catch {
            /* ignore */
          }
        };
        ws.onerror = () => {
          ws?.close();
        };
      } catch {
        if (unmounted) return;
        setConnected(false);
        scheduleReconnect();
      }
    }

    connect();
    return () => {
      unmounted = true;
      if (retry) clearTimeout(retry);
      ws?.close();
    };
  }, []);

  return { connected, reconnecting };
}
