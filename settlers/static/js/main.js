import { h, render } from 'preact';
import { useEffect, useRef, useState } from 'preact/hooks';
import htm from 'htm';
import { api, useSession } from './api.js';
import { Board } from './board.js';
import { GameScreen } from './game.js';
import { LinkBox } from './ui.js';

const html = htm.bind(h);

function SetupScreen({ onCreated, onError }) {
  const [board, setBoard] = useState(null);
  const [colour, setColour] = useState('red');
  const [busy, setBusy] = useState(false);

  const run = async (fn) => {
    setBusy(true);
    try { await fn(); } catch (e) { onError(e.message); } finally { setBusy(false); }
  };

  useEffect(() => { run(async () => setBoard((await api('GET', '/api/setup')).board)); }, []);

  return html`<main class="setup">
    <header class="topbar"><h1>Settlers</h1><span class="subtitle">New game</span></header>
    <section class="board-wrap">
      ${board ? html`<${Board} board=${board} />` : html`<p>Loading…</p>`}
    </section>
    <div class="actions">
      <button disabled=${busy}
        onClick=${() => run(async () => setBoard((await api('POST', '/api/setup/regenerate')).board))}>
        Regenerate</button>
      <span class="colour-pick">Play as
        ${['red', 'blue'].map((c) => html`<label key=${c}>
          <input type="radio" name="colour" checked=${colour === c} onChange=${() => setColour(c)} />
          <span class=${'swatch p-' + c}></span>${c}</label>`)}
      </span>
      <button class="primary" disabled=${busy || !board}
        onClick=${() => run(async () => onCreated(await api('POST', '/api/game', { colour })))}>
        Create game</button>
    </div>
  </main>`;
}

function WaitingScreen({ session }) {
  return html`<main class="setup">
    <header class="topbar"><h1>Settlers</h1><span class="subtitle">Waiting for your opponent</span></header>
    <div class="panel invite">
      ${session.invite_link
        ? html`<${LinkBox} label="Send this invite link to your opponent:" url=${session.invite_link} />`
        : html`<p>Waiting for the other player to join.</p>`}
    </div>
    <section class="board-wrap"><${Board} board=${session.board} /></section>
  </main>`;
}

function App() {
  const { session, setSession, connected, reconnect } = useSession();
  const [error, setError] = useState(null);
  const timer = useRef(null);
  const showError = (msg) => {
    setError(msg);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setError(null), 4000);
  };

  let screen;
  if (!session) screen = html`<p class="message-page">Loading…</p>`;
  else if (session.status === 'none') {
    screen = html`<${SetupScreen} onError=${showError}
      onCreated=${(view) => { setSession(view); reconnect(); }} />`;
  } else if (session.status === 'occupied') {
    screen = html`<main class="message-page"><h1>Settlers</h1>
      <p>A game is in progress. Use your player link to rejoin it.</p></main>`;
  } else if (session.status === 'waiting') {
    screen = html`<${WaitingScreen} session=${session} />`;
  } else {
    screen = html`<${GameScreen} session=${session} onError=${showError} />`;
  }

  return html`<div>
    ${screen}
    ${error && html`<div class="toast">${error}</div>`}
    ${!connected && session && html`<div class="offline">Reconnecting…</div>`}
  </div>`;
}

render(html`<${App} />`, document.getElementById('app'));
