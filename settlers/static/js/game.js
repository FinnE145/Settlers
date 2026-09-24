// The in-game screen: opponent bar, board, your bar, side panel and pop-ups.
import { h } from 'preact';
import { useEffect, useRef, useState } from 'preact/hooks';
import htm from 'htm';
import { Board, Pieces, Targets } from './board.js';
import { api } from './api.js';
import { NAMES, OpponentBar, PlayerBar } from './hud.js';
import { Die, ResCard, ResGlyph } from './icons.js';
import { LinkBox, RESOURCES, emptyCards, total } from './ui.js';

const html = htm.bind(h);

const TARGET_KIND = {
  settlement: 'vertex', city: 'vertex', road: 'edge', ship: 'edge', robber: 'hex', pirate: 'hex',
};
const BUILD_ACTION = {
  settlement: ['build_settlement', 'vertex'],
  city: ['build_city', 'vertex'],
  road: ['build_road', 'edge'],
  ship: ['build_ship', 'edge'],
};
const LABEL = { road: 'Road', ship: 'Ship', settlement: 'Settlement', city: 'City' };

const canAfford = (hand, cost) => Object.entries(cost).every(([r, n]) => hand[r] >= n);

function victimAt(board, game, piece, hex, me) {
  const o = 1 - me;
  if (piece === 'robber') {
    return board.hexes[hex].corners.some((v) => game.buildings.some((b) => b.vertex === v && b.owner === o));
  }
  return board.hexes[hex].edges.some((e) =>
    game.routes.some((r) => r.edge === e && r.owner === o && r.kind === 'ship'));
}

function promptText(game, me) {
  if (game.phase === 'finished') return game.winner === me ? 'You win!' : `${NAMES[game.winner]} wins.`;
  const discardsWaiting = game.pending.some((p) => p.type === 'discard');
  const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
  for (const p of game.pending.filter((q) => q.player === me)) {
    if (p.type === 'discard') return `Discard ${plural(p.count, 'card')}.`;
    if (p.type === 'gold') return `Pick ${plural(p.count, 'card')} from gold.`;
    if (p.type === 'robber') return discardsWaiting ? 'Waiting for discards…' : 'Move the robber or the pirate.';
    if (p.type === 'free_routes') return `Place ${p.count} free road${p.count === 1 ? '' : 's'} or ships.`;
  }
  const other = game.pending.find((p) => p.player !== me);
  if (other) return `Waiting for ${NAMES[other.player]}…`;
  if (game.phase === 'setup') {
    if (game.setup.player !== me) return `${NAMES[game.setup.player]} is placing.`;
    return game.setup.awaiting === 'settlement' ? 'Place a settlement.' : 'Place a road or ship next to it.';
  }
  if (game.current !== me) return `${NAMES[game.current]}'s turn.`;
  return game.rolled ? 'Your turn.' : 'Your turn: roll the dice.';
}

// ---------------------------------------------------------------- pop-ups

function Popup({ title, children }) {
  return html`<div class="popup"><div class="popup-title">${title}</div>${children}</div>`;
}

/** Click cards to pick them; the small − under a card takes one back. */
function CardSelect({ count, available, onSubmit, label }) {
  const [value, setValue] = useState(emptyCards());
  const sum = total(value);
  return html`<div>
    <div class="select-row">
      ${RESOURCES.map((r) => {
        const left = available ? available[r] - value[r] : Infinity;
        const can = sum < count && left > 0;
        return html`<div key=${r} class="select-card">
          <button class="card-btn" disabled=${!can} onClick=${() => setValue({ ...value, [r]: value[r] + 1 })}>
            <${ResCard} res=${r} count=${available ? available[r] : null} dim=${available && available[r] === 0} />
          </button>
          <div class="select-count">
            ${value[r] > 0
              ? html`<button class="small" onClick=${() => setValue({ ...value, [r]: value[r] - 1 })}>−</button>
                  <b>${value[r]}</b>`
              : html`<span class="muted">·</span>`}
          </div>
        </div>`;
      })}
    </div>
    <div class="popup-actions">
      <span class="muted">${sum} / ${count}</span>
      <button class="primary" disabled=${sum !== count} onClick=${() => onSubmit(value)}>${label}</button>
    </div>
  </div>`;
}

function RobberPopup({ board, game, me, piece, setPiece, hex, send }) {
  const victim = hex != null && victimAt(board, game, piece, hex, me);
  const oppCards = game.players[1 - me].hand_count;
  const move = (take) => send({ type: 'move_robber', piece, hex, take });
  return html`<${Popup} title=${`Move the ${piece}`}>
    <div class="toggle">
      <button class=${piece === 'robber' ? 'active' : ''} onClick=${() => setPiece('robber')}>Robber</button>
      <button class=${piece === 'pirate' ? 'active' : ''} onClick=${() => setPiece('pirate')}>Pirate</button>
    </div>
    ${hex == null
      ? html`<p class="muted">Click a highlighted hex on the board.</p>`
      : html`<div>
          ${victim && html`<button class="primary steal" disabled=${oppCards === 0} onClick=${() => move('steal')}>
            Steal a random card from ${NAMES[1 - me]} (${oppCards})</button>`}
          <div class="muted small-gap">${victim ? 'or take' : 'Take'} one from the supply:</div>
          <div class="select-row">
            ${RESOURCES.map((r) => html`<button key=${r} class="card-btn" onClick=${() => move(r)}>
              <${ResCard} res=${r} badge=${false} /></button>`)}
          </div>
        </div>`}
  <//>`;
}

// ---------------------------------------------------------------- side panel

function Dice({ dice, current }) {
  if (!dice) return html`<div class="dice-box muted">No roll yet</div>`;
  return html`<div class=${'dice-box' + (current ? '' : ' stale')}>
    <${Die} value=${dice[0]} /><${Die} value=${dice[1]} />
    <span class="dice-total">${dice[0] + dice[1]}</span>
  </div>`;
}

function MiniCost({ cost }) {
  return html`<span class="mini-cost">${Object.entries(cost).flatMap(([r, n]) =>
    Array.from({ length: n }, (_, i) => html`<span key=${r + i} class=${'mini-card c-' + r}>
      <${ResGlyph} res=${r} size=${11} /></span>`))}</span>`;
}

function BuildButtons({ game, me, mode, setMode, kinds, free }) {
  const hand = game.players[me].hand;
  return html`<div class="build">
    ${kinds.map((k) => {
      const affordable = free || canAfford(hand, game.costs[k]);
      const possible = (game.legal[k] || []).length > 0;
      return html`<button key=${k} class=${'build-btn' + (mode === k ? ' active' : '')}
        disabled=${!affordable || !possible} onClick=${() => setMode(mode === k ? null : k)}>
        <span>${LABEL[k]}</span>${!free && html`<${MiniCost} cost=${game.costs[k]} />`}
      </button>`;
    })}
  </div>`;
}

function Log({ entries }) {
  const ref = useRef(null);
  useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, [entries.length]);
  return html`<div class="log" ref=${ref}>
    ${entries.map((e) => html`<div key=${e.n}>${e.text.split(/\b(Red|Blue)\b/).map((part, i) =>
      (i % 2 ? html`<b class=${'name-' + part.toLowerCase()}>${part}</b>` : part))}</div>`)}
  </div>`;
}

// ---------------------------------------------------------------- screen

export function GameScreen({ session, onError }) {
  const { board, game, seat: me } = session;
  const [mode, setMode] = useState(null);
  const [robberHex, setRobberHex] = useState(null);
  const legal = game.legal || {};
  const mine = game.pending.filter((p) => p.player === me);
  const pendingOf = (type) => mine.find((p) => p.type === type);
  const gold = pendingOf('gold');
  const discard = pendingOf('discard');
  const discardsWaiting = game.pending.some((p) => p.type === 'discard');
  const robberDue = pendingOf('robber') && !discardsWaiting;
  const freeRoutes = pendingOf('free_routes');
  const myTurn = game.phase === 'play' && game.current === me;
  const mainPhase = myTurn && game.rolled && game.pending.length === 0;
  const setupRoute = game.phase === 'setup' && game.setup.player === me && game.setup.awaiting === 'route';

  // Forced placements pick their own mode; otherwise use what the player chose.
  let active = mode;
  if (game.phase === 'setup' && game.setup.player === me) {
    if (game.setup.awaiting === 'settlement') active = 'settlement';
    else if (mode !== 'road' && mode !== 'ship') active = (legal.road || []).length ? 'road' : 'ship';
  } else if (robberDue) {
    if (mode !== 'robber' && mode !== 'pirate') active = 'robber';
  } else if (active && !(legal[active] || []).length) {
    active = null;
  }

  const send = async (action) => {
    try {
      await api('POST', '/api/action', { action });
      setMode(null);
      setRobberHex(null);
    } catch (e) {
      onError(e.message);
    }
  };

  const onPick = (id) => {
    if (BUILD_ACTION[active]) {
      const [type, key] = BUILD_ACTION[active];
      send({ type, [key]: id });
    } else if (active === 'robber' || active === 'pirate') {
      setRobberHex(id);
    }
  };
  const chooseMode = (m) => { setMode(m); setRobberHex(null); };

  let popup = null;
  if (gold) {
    popup = html`<${Popup} title=${`Pick ${gold.count} from gold`}>
      <${CardSelect} key=${'g' + game.log.length} count=${gold.count} label="Take"
        onSubmit=${(cards) => send({ type: 'choose_gold', cards })} />
    <//>`;
  } else if (discard) {
    popup = html`<${Popup} title=${`Discard ${discard.count} (half your hand)`}>
      <${CardSelect} key=${'d' + game.log.length} count=${discard.count} available=${game.players[me].hand}
        label="Discard" onSubmit=${(cards) => send({ type: 'discard', cards })} />
    <//>`;
  } else if (robberDue) {
    popup = html`<${RobberPopup} board=${board} game=${game} me=${me} piece=${active === 'pirate' ? 'pirate' : 'robber'}
      setPiece=${chooseMode} hex=${robberHex} send=${send} />`;
  }

  const roll = game.rolled && game.dice ? game.dice[0] + game.dice[1] : null;
  const myMove = myTurn || mine.length > 0 || (game.phase === 'setup' && game.setup.player === me);
  useEffect(() => {
    document.title = myMove && game.phase !== 'finished' ? '● Your move · Settlers' : 'Settlers';
    return () => { document.title = 'Settlers'; };
  }, [myMove, game.phase]);

  return html`<div class="table">
    <${OpponentBar} game=${game} p=${1 - me} />
    <section class="board-area">
      <${Board} board=${board} roll=${roll} robber=${game.robber}>
        <${Pieces} board=${board} game=${game} />
        ${active && html`<${Targets} board=${board} kind=${TARGET_KIND[active]} ids=${legal[active]}
          selected=${robberHex} onPick=${onPick} />`}
      <//>
      ${popup && html`<div class="popup-anchor">${popup}</div>`}
    </section>
    <${PlayerBar} game=${game} p=${me} />

    <aside class="side">
      <div class=${'prompt' + (myMove ? ' mine' : '')}>
        ${promptText(game, me)}
      </div>
      <${Dice} dice=${game.dice} current=${game.rolled} />
      <div class="turn-buttons">
        ${myTurn && !game.rolled && html`<button class="primary big" disabled=${game.pending.length > 0}
          onClick=${() => send({ type: 'roll' })}>Roll dice</button>`}
        ${mainPhase && html`<button class="big" onClick=${() => send({ type: 'end_turn' })}>End turn</button>`}
      </div>
      ${setupRoute && !gold && html`<${BuildButtons} game=${game} me=${me} mode=${active} setMode=${chooseMode}
        kinds=${['road', 'ship']} free />`}
      ${freeRoutes && html`<${BuildButtons} game=${game} me=${me} mode=${active} setMode=${chooseMode}
        kinds=${['road', 'ship']} free />`}
      ${mainPhase && html`<${BuildButtons} game=${game} me=${me} mode=${active} setMode=${chooseMode}
        kinds=${['road', 'ship', 'settlement', 'city']} />`}
      <${Log} entries=${game.log} />
      <details class="links">
        <summary>Game</summary>
        <${LinkBox} label="Your link (to rejoin from another device)" url=${session.my_link} />
        <button class="danger" onClick=${() => {
          if (confirm('End this game for both players?')) api('POST', '/api/abandon').catch((e) => onError(e.message));
        }}>End game</button>
      </details>
    </aside>
  </div>`;
}
