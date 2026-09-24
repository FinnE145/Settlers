import { useEffect, useRef, useState } from 'preact/hooks';

export async function api(method, url, body) {
  const res = await fetch(url, {
    method,
    credentials: 'same-origin',
    headers: method === 'GET' ? {} : { 'Content-Type': 'application/json' },
    body: method === 'GET' ? undefined : JSON.stringify(body ?? {}),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

/** The current session, kept live over a WebSocket. ``reconnect`` is needed after the
 * seat cookie changes (the socket identifies the player when it connects). */
export function useSession() {
  const [session, setSession] = useState(null);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef(null);
  const generation = useRef(0);

  const connect = () => {
    const gen = ++generation.current;
    if (socketRef.current) socketRef.current.close();
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${location.host}/ws`);
    socketRef.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === 'session') setSession(msg.data);
    };
    ws.onclose = () => {
      if (gen !== generation.current) return;
      setConnected(false);
      setTimeout(() => { if (gen === generation.current) connect(); }, 1500);
    };
  };

  useEffect(() => {
    api('GET', '/api/session').then(setSession).catch(() => {});
    connect();
    return () => { generation.current++; socketRef.current?.close(); };
  }, []);

  return { session, setSession, connected, reconnect: connect };
}
