"use client";

import { useEffect, useRef, useState } from "react";
import { wsUrl } from "@/lib/api";

export type WsMessage = { event: string; payload?: Record<string, unknown> } & Record<string, unknown>;

type Handlers = {
  onMessage?: (msg: WsMessage) => void;
  onOpen?: () => void;
  onClose?: () => void;
};

export function useMarketWebSocket(handlers: Handlers) {
  const [connected, setConnected] = useState(false);
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      try {
        ws = new WebSocket(wsUrl());
        ws.onopen = () => {
          setConnected(true);
          handlersRef.current.onOpen?.();
        };
        ws.onclose = () => {
          setConnected(false);
          handlersRef.current.onClose?.();
          retry = setTimeout(connect, 3000);
        };
        ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data) as WsMessage;
            handlersRef.current.onMessage?.(msg);
          } catch {
            /* ignore */
          }
        };
      } catch {
        setConnected(false);
        retry = setTimeout(connect, 5000);
      }
    }

    connect();
    return () => {
      if (retry) clearTimeout(retry);
      ws?.close();
    };
  }, []);

  return { connected };
}
