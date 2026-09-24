import { h, render } from 'preact';
import { useEffect, useState } from 'preact/hooks';
import htm from 'htm';
import { Board } from './board.js';

const html = htm.bind(h);

async function api(method, url, body) {
  const res = await fetch(url, {
    method,
    credentials: 'same-origin',
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

function SetupScreen() {
  const [board, setBoard] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const load = async (method, url) => {
    setBusy(true);
    try {
      setBoard((await api(method, url)).board);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { load('GET', '/api/setup'); }, []);

  return html`<main class="setup">
    <header class="topbar"><h1>Settlers</h1><span class="subtitle">New game</span></header>
    ${error && html`<p class="error">${error}</p>`}
    <section class="board-wrap">
      ${board ? html`<${Board} board=${board} />` : html`<p>Loading…</p>`}
    </section>
    <div class="actions">
      <button onClick=${() => load('POST', '/api/setup/regenerate')} disabled=${busy}>Regenerate</button>
      <button class="primary" disabled title="Coming next">Create game</button>
    </div>
  </main>`;
}

render(html`<${SetupScreen} />`, document.getElementById('app'));
