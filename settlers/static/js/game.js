// The in-game screen: board with pieces and targets, and the sidebar.
import { h } from 'preact';
import { useEffect, useRef, useState } from 'preact/hooks';
import htm from 'htm';
import { Board, COLOURS, Pieces, Targets } from './board.js';
import { api } from './api.js';
import { CardPicker, Cards, Cost, LinkBox, RESOURCES, emptyCards, total } from './ui.js';

const html = htm.bind(h);
export const NAMES = ['Red', 'Blue'];

const TARGET_KIND = {
  settlement: 'vertex', city: 'vertex', road: 'edge', ship: 'edge', robber: 'hex', pirate: 'hex',
};
const BUILD_ACTION = {
  settlement: ['build_settlement', 'vertex'],
  city: ['build_city', 'vertex'],
  road: ['build_road', 'edge'],
  ship: ['build_ship', 'edge'],
};

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
  for (const p of game.pending.filter((q) => q.player === me)) {
    if (p.type === 'discard') return `Discard ${p.count} card${p.count > 1 ? 's' : ''}.`;
    if (p.type === 'gold') return `Pick ${p.count} card${p.count > 1 ? 's' : ''} from gold.`;
    if (p.type === 'robber') return discardsWaiting ? 'Waiting for discards…' : 'Move the robber or the pirate.';
    if (p.type === 'free_routes') return `Place ${p.count} free road${p.count > 1 ? 's' : ''} or ship${p.count > 1 ? 's' : ''}.`;
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

// ---------------------------------------------------------------- panels

function PlayerCard({ p, i, me, game }) {
  const active = game.phase === 'setup' ? game.setup.player === i : game.phase === 'play' && game.current === i;
  const vp = p.total_vp != null && p.total_vp !== p.vp ? `${p.vp} (${p.total_vp})` : p.vp;
  return html`<div class=${`player-card pc-${COLOURS[i]}${active ? ' active' : ''}`}>
    <div class="pc-head">
      <span class=${'swatch p-' + COLOURS[i]}></span>
      <b>${NAMES[i]}${i === me ? ' (you)' : ''}</b>
      <span class="vp">${vp} / ${p.vp_needed} VP</span>
    </div>
    <div class="pc-stats">Cards ${p.hand_count} · Bank ${p.bank_count} · Fish ${p.fish_count} · Dev ${p.dev_count}</div>
    <div class="pc-stats">Knights ${p.knights} · Route ${p.route_length} · Settlements ${p.settlements} · Cities ${p.cities}</div>
    <div class="badges">
      ${p.longest_route && html`<span class="badge">Longest route</span>`}
      ${p.largest_army && html`<span class="badge">Largest army</span>`}
      ${p.boot && html`<span class="badge boot">Old boot</span>`}
    </div>
  </div>`;
}

function Dice({ dice }) {
  if (!dice) return null;
  return html`<span class="dice">${dice.map((d, i) => html`<span key=${i} class="die">${d}</span>`)}
    <span class="dice-total">= ${dice[0] + dice[1]}</span></span>`;
}

function BuildButtons({ game, me, mode, setMode, free }) {
  const hand = game.players[me].hand;
  const legal = game.legal;
  const kinds = free || game.phase === 'setup' ? ['road', 'ship'] : ['road', 'ship', 'settlement', 'city'];
  return html`<div class="build">
    ${kinds.map((k) => {
      const affordable = free || game.phase === 'setup' || canAfford(hand, game.costs[k]);
      const possible = (legal[k] || []).length > 0;
      return html`<button key=${k} class=${mode === k ? 'active' : ''} disabled=${!affordable || !possible}
        onClick=${() => setMode(mode === k ? null : k)}>
        ${k[0].toUpperCase() + k.slice(1)}
        ${!free && game.phase !== 'setup' && html` <${Cost} cost=${game.costs[k]} />`}
      </button>`;
    })}
  </div>`;
}

function PickPanel({ title, count, available, onSubmit, label }) {
  const [value, setValue] = useState(emptyCards());
  return html`<div class="panel">
    <div class="panel-title">${title}</div>
    <${CardPicker} value=${value} onChange=${setValue} available=${available} max=${count} />
    <button class="primary" disabled=${total(value) !== count} onClick=${() => onSubmit(value)}>${label}</button>
  </div>`;
}

function RobberPanel({ board, game, me, mode, setMode, hex, send }) {
  const piece = mode === 'pirate' ? 'pirate' : 'robber';
  const victim = hex != null && victimAt(board, game, piece, hex, me);
  const oppCards = game.players[1 - me].hand_count;
  const move = (take) => send({ type: 'move_robber', piece, hex, take });
  return html`<div class="panel">
    <div class="panel-title">Move the ${piece}</div>
    <div class="build">
      <button class=${piece === 'robber' ? 'active' : ''} onClick=${() => setMode('robber')}>Robber</button>
      <button class=${piece === 'pirate' ? 'active' : ''} onClick=${() => setMode('pirate')}>Pirate</button>
    </div>
    ${hex == null
      ? html`<p class="muted">Click a highlighted hex.</p>`
      : html`<div>
          ${victim && html`<button disabled=${oppCards === 0} onClick=${() => move('steal')}>
            Steal from ${NAMES[1 - me]} (${oppCards} cards)</button>`}
          <div class="muted small-gap">or take from the supply:</div>
          <div class="build">${RESOURCES.map((r) => html`<button key=${r} class=${'res-btn r-' + r}
            onClick=${() => move(r)}>${r}</button>`)}</div>
        </div>`}
  </div>`;
}

function Log({ entries }) {
  const ref = useRef(null);
  useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, [entries.length]);
  return html`<div class="log" ref=${ref}>
    ${entries.map((e) => html`<div key=${e.n}>${e.text}</div>`)}
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
  const discardsWaiting = game.pending.some((p) => p.type === 'discard');
  const robberDue = pendingOf('robber') && !discardsWaiting;
  const freeRoutes = pendingOf('free_routes');
  const myTurn = game.phase === 'play' && game.current === me;
  const mainPhase = myTurn && game.rolled && game.pending.length === 0;

  // Forced placements pick their own mode; otherwise use what the player chose.
  let active = mode;
  if (game.phase === 'setup' && game.setup.player === me && !pendingOf('gold')) {
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
  const gold = pendingOf('gold');
  const discard = pendingOf('discard');
  const me_ = game.players[me];

  return html`<div class="game">
    <section class="board-area">
      <${Board} board=${board}>
        <${Pieces} board=${board} game=${game} />
        ${active && html`<${Targets} board=${board} kind=${TARGET_KIND[active]} ids=${legal[active]}
          selected=${robberHex} onPick=${onPick} />`}
      <//>
    </section>
    <aside class="sidebar">
      ${game.players.map((p, i) => html`<${PlayerCard} key=${i} p=${p} i=${i} me=${me} game=${game} />`)}

      <div class="panel turn">
        <div class="prompt">${promptText(game, me)}</div>
        <${Dice} dice=${game.dice} />
        <div class="build">
          ${myTurn && !game.rolled && html`<button class="primary" disabled=${game.pending.length > 0}
            onClick=${() => send({ type: 'roll' })}>Roll dice</button>`}
          ${mainPhase && html`<button onClick=${() => send({ type: 'end_turn' })}>End turn</button>`}
        </div>
      </div>

      ${game.phase === 'setup' && game.setup.player === me && game.setup.awaiting === 'route' && !gold
        && html`<div class="panel"><${BuildButtons} game=${game} me=${me} mode=${active} setMode=${chooseMode} /></div>`}
      ${(mainPhase || freeRoutes) && html`<div class="panel">
        <${BuildButtons} game=${game} me=${me} mode=${active} setMode=${chooseMode} free=${!!freeRoutes} />
      </div>`}
      ${gold && html`<${PickPanel} key=${'gold' + game.log.length} title=${`Pick ${gold.count} from gold`}
        count=${gold.count} label="Take" onSubmit=${(cards) => send({ type: 'choose_gold', cards })} />`}
      ${discard && html`<${PickPanel} key=${'discard' + game.log.length} title=${`Discard ${discard.count}`}
        count=${discard.count} available=${me_.hand} label="Discard"
        onSubmit=${(cards) => send({ type: 'discard', cards })} />`}
      ${robberDue && html`<${RobberPanel} board=${board} game=${game} me=${me} mode=${active}
        setMode=${chooseMode} hex=${robberHex} send=${send} />`}

      <div class="panel">
        <div class="panel-title">Your hand</div>
        <${Cards} cards=${me_.hand} empty="No cards" />
        <div class="small-gap">Fish: ${me_.fish.length ? me_.fish.join(', ') + ` (${me_.fish.reduce((a, b) => a + b, 0)} total)` : 'none'}</div>
      </div>

      <${Log} entries=${game.log} />

      <div class="panel footer">
        <${LinkBox} label="Your link (to rejoin from another device)" url=${session.my_link} />
        <button class="danger" onClick=${() => {
          if (confirm('End this game for both players?')) api('POST', '/api/abandon').catch((e) => onError(e.message));
        }}>End game</button>
      </div>
    </aside>
  </div>`;
}
