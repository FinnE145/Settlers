// The in-game screen: opponent bar, board, your bar, side panel and pop-ups.
import { h } from 'preact';
import { useEffect, useLayoutEffect, useRef, useState } from 'preact/hooks';
import htm from 'htm';
import { Board, Pieces, Targets } from './board.js';
import { api } from './api.js';
import { COLOURS, OpponentBar, PlayerBar } from './hud.js';
import { Die, ResGlyph } from './icons.js';
import {
  CardSelect, DepositPopup, FishPopup, MonopolyPopup, MyOfferPopup, OfferPopup, Popup,
  RobberPopup, TradePopup, YearOfPlentyPopup,
} from './popups.js';
import { LinkBox } from './ui.js';

const html = htm.bind(h);

const TARGET_KIND = {
  settlement: 'vertex', city: 'vertex', road: 'edge', ship: 'edge', robber: 'hex', pirate: 'hex',
  move_ship: 'edge', ship_target: 'edge', route: 'edge',
};
const BUILD_ACTION = {
  settlement: ['build_settlement', 'vertex'],
  city: ['build_city', 'vertex'],
  road: ['build_road', 'edge'],
  ship: ['build_ship', 'edge'],
};
const LABEL = { road: 'Road', ship: 'Ship', settlement: 'Settlement', city: 'City' };

const canAfford = (hand, cost) => Object.entries(cost).every(([r, n]) => hand[r] >= n);

function promptText(game, me) {
  if (game.phase === 'finished') return game.winner === me ? 'You win!' : `${game.names[game.winner]} wins.`;
  const discardsWaiting = game.pending.some((p) => p.type === 'discard');
  const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
  for (const p of game.pending.filter((q) => q.player === me)) {
    if (p.type === 'discard') return `Discard ${plural(p.count, 'card')}.`;
    if (p.type === 'gold') return `Pick ${plural(p.count, 'card')} from gold.`;
    if (p.type === 'robber') return discardsWaiting ? 'Waiting for discards…' : 'Move the robber or the pirate.';
    if (p.type === 'free_routes') return `Place ${p.count} free ${p.count === 1 ? 'road or ship' : 'roads or ships'}.`;
  }
  const other = game.pending.find((p) => p.player !== me);
  if (other) return `Waiting for ${game.names[other.player]}…`;
  if (game.phase === 'setup') {
    if (game.setup.player !== me) return `${game.names[game.setup.player]} is placing.`;
    return game.setup.awaiting === 'settlement' ? 'Place a settlement.' : 'Place a road or ship next to it.';
  }
  if (game.current !== me) return `${game.names[game.current]}'s turn.`;
  return game.rolled ? 'Your turn.' : 'Your turn: roll the dice.';
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

/** Log lines refer to players as {0} and {1}; show their names in their colours. */
function Log({ entries, names }) {
  const ref = useRef(null);
  useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, [entries.length]);
  return html`<div class="log" ref=${ref}>
    ${entries.map((e) => html`<div key=${e.n}>${e.text.split(/\{(\d)\}/).map((part, i) =>
      (i % 2 ? html`<b class=${'name-' + COLOURS[+part]}>${names[+part]}</b>` : part))}</div>`)}
  </div>`;
}

// ---------------------------------------------------------------- screen

const OFFSET_KEY = 'settlers-popup-offset';

function loadOffset() {
  try {
    const o = JSON.parse(localStorage.getItem(OFFSET_KEY));
    if (o && Number.isFinite(o.x) && Number.isFinite(o.y)) return o;
  } catch { /* ignore */ }
  return { x: 0, y: 0 };
}

function saveOffset(o) {
  try { localStorage.setItem(OFFSET_KEY, JSON.stringify(o)); } catch { /* ignore */ }
}

const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);

/** Pop-ups can be dragged by their title bar; where you leave them is where the next
 * ones open. Double-clicking the title bar puts them back at the bottom middle. They are
 * always kept fully on the board. */
function usePopupDrag() {
  const [offset, setOffset] = useState(loadOffset);
  const anchor = useRef(null);
  const current = useRef(offset);
  current.current = offset;

  // A saved spot may not fit a bigger pop-up or a smaller window: nudge it back inside.
  useLayoutEffect(() => {
    const el = anchor.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const a = el.parentElement.getBoundingClientRect();
    let dx = 0;
    let dy = 0;
    if (r.width <= a.width) dx = r.left < a.left ? a.left - r.left : r.right > a.right ? a.right - r.right : 0;
    if (r.height <= a.height) dy = r.top < a.top ? a.top - r.top : r.bottom > a.bottom ? a.bottom - r.bottom : 0;
    if (dx || dy) setOffset((o) => ({ x: o.x + dx, y: o.y + dy }));
  });

  const onPointerDown = (e) => {
    if (e.button !== 0 || !e.target.closest('.popup-head') || e.target.closest('button')) return;
    e.preventDefault();
    const start = {
      x: e.clientX, y: e.clientY, from: current.current,
      rect: anchor.current.getBoundingClientRect(), area: anchor.current.parentElement.getBoundingClientRect(),
    };
    const move = (ev) => {
      const dx = clamp(ev.clientX - start.x, start.area.left - start.rect.left, start.area.right - start.rect.right);
      const dy = clamp(ev.clientY - start.y, start.area.top - start.rect.top, start.area.bottom - start.rect.bottom);
      setOffset({ x: start.from.x + dx, y: start.from.y + dy });
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      window.removeEventListener('pointercancel', up);
      saveOffset(current.current);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
    window.addEventListener('pointercancel', up);
  };
  const onDblClick = (e) => {
    if (!e.target.closest('.popup-head') || e.target.closest('button')) return;
    setOffset({ x: 0, y: 0 });
    saveOffset({ x: 0, y: 0 });
  };
  const style = { transform: `translate(calc(-50% + ${offset.x}px), ${offset.y}px)` };
  return { ref: anchor, style, onPointerDown, onDblClick };
}

export function GameScreen({ session, onError }) {
  const { board, game, seat: me } = session;
  const [mode, setMode] = useState(null);
  const [robberHex, setRobberHex] = useState(null);
  const [shipFrom, setShipFrom] = useState(null);
  const [coastKind, setCoastKind] = useState('road'); // what a coastal edge gets when either fits
  const [panel, setPanel] = useState(null); // {kind, ...} for pop-ups the player opens
  const legal = game.legal || {};
  const info = game.players[me];
  const mine = game.pending.filter((p) => p.player === me);
  const pendingOf = (type) => mine.find((p) => p.type === type);
  const gold = pendingOf('gold');
  const discard = pendingOf('discard');
  const discardsWaiting = game.pending.some((p) => p.type === 'discard');
  const robberDue = pendingOf('robber') && !discardsWaiting;
  const freeRoutes = pendingOf('free_routes');
  const myTurn = game.phase === 'play' && game.current === me;
  const mainPhase = myTurn && game.rolled && game.pending.length === 0;
  const tradeWindow = game.phase === 'play' && game.rolled && game.pending.length === 0;
  const setupRoute = game.phase === 'setup' && game.setup.player === me && game.setup.awaiting === 'route';

  // Starting and free roads/ships show every road and ship spot at once.
  const routePlacing = (setupRoute && !gold) || Boolean(freeRoutes);
  const roadSpots = new Set(legal.road || []);
  const shipSpots = new Set(legal.ship || []);

  // Forced placements pick their own mode; otherwise use what the player chose.
  let active = mode;
  if (game.phase === 'setup' && game.setup.player === me) {
    active = game.setup.awaiting === 'settlement' ? 'settlement' : 'route';
  } else if (routePlacing) {
    active = 'route';
  } else if (robberDue) {
    if (mode !== 'robber' && mode !== 'pirate') active = 'robber';
  } else if (active === 'move_ship') {
    if (!(legal.move_ship || []).length) active = null;
  } else if (active && !(legal[active] || []).length) {
    active = null;
  }
  // Ship moves pick a ship first, then where it goes.
  let targets = active && legal[active];
  if (active === 'route') targets = [...new Set([...roadSpots, ...shipSpots])];
  if (active === 'move_ship' && shipFrom != null) targets = (legal.ship_targets || {})[shipFrom] || [];

  const reset = () => { setMode(null); setRobberHex(null); setShipFrom(null); };
  const send = async (action) => {
    try {
      await api('POST', '/api/action', { action });
      reset();
      return true;
    } catch (e) {
      onError(e.message);
      return false;
    }
  };

  const onPick = (id) => {
    if (active === 'route') {
      const kind = roadSpots.has(id) && shipSpots.has(id) ? coastKind : roadSpots.has(id) ? 'road' : 'ship';
      send({ type: `build_${kind}`, edge: id });
    } else if (BUILD_ACTION[active]) {
      const [type, key] = BUILD_ACTION[active];
      send({ type, [key]: id });
    } else if (active === 'robber' || active === 'pirate') {
      setRobberHex(id);
    } else if (active === 'move_ship') {
      if (shipFrom == null) setShipFrom(id);
      else send({ type: 'move_ship', from: shipFrom, to: id });
    }
  };
  const chooseMode = (m) => { setMode(m); setRobberHex(null); setShipFrom(null); };
  const close = () => setPanel(null);
  const popupDrag = usePopupDrag();

  const playDev = (card) => {
    if (card === 'year_of_plenty') setPanel({ kind: 'yop' });
    else if (card === 'monopoly') setPanel({ kind: 'monopoly' });
    else send({ type: 'play_dev', card });
  };

  // Close player-opened pop-ups that no longer make sense.
  useEffect(() => {
    if (!panel) return;
    const stillOk = {
      trade: tradeWindow, fish: mainPhase, deposit: game.phase === 'play' && game.pending.length === 0,
      yop: myTurn && !game.dev_played, monopoly: myTurn && !game.dev_played,
    }[panel.kind];
    if (!stillOk) setPanel(null);
  }, [panel, tradeWindow, mainPhase, myTurn, game.dev_played, game.pending.length, game.phase]);

  let popup = null;
  if (game.phase === 'finished') {
    popup = html`<${Popup} title=${game.winner === me ? 'You win!' : `${game.names[game.winner]} wins`}>
      <div class="final">
        ${game.players.map((p, i) => html`<div key=${i} class=${'final-row name-' + p.colour}>
          <b>${game.names[i]}</b> <span>${p.vp} VP</span>
        </div>`)}
      </div>
      <div class="popup-actions">
        <button class="primary" onClick=${() => api('POST', '/api/abandon').catch((e) => onError(e.message))}>
          New game</button>
      </div>
    <//>`;
  } else if (gold) {
    popup = html`<${Popup} title=${`Pick ${gold.count} from gold`}>
      <${CardSelect} key=${'g' + game.log.length} count=${gold.count} label="Take"
        onSubmit=${(cards) => send({ type: 'choose_gold', cards })} />
    <//>`;
  } else if (discard) {
    popup = html`<${Popup} title=${`Discard ${discard.count} (half your hand)`}>
      <${CardSelect} key=${'d' + game.log.length} count=${discard.count} available=${info.hand}
        label="Discard" onSubmit=${(cards) => send({ type: 'discard', cards })} />
    <//>`;
  } else if (robberDue) {
    popup = html`<${RobberPopup} board=${board} game=${game} me=${me} piece=${active === 'pirate' ? 'pirate' : 'robber'}
      setPiece=${chooseMode} hex=${robberHex} send=${send} />`;
  } else if (panel?.kind === 'yop') {
    popup = html`<${YearOfPlentyPopup} send=${send} onClose=${close} />`;
  } else if (panel?.kind === 'monopoly') {
    popup = html`<${MonopolyPopup} send=${send} onClose=${close} />`;
  } else if (game.trade && game.trade.from !== me && tradeWindow && panel?.kind !== 'trade') {
    popup = html`<${OfferPopup} game=${game} me=${me} send=${send}
      onCounter=${(offer) => setPanel({ kind: 'trade', initial: offer })} />`;
  } else if (panel?.kind === 'trade') {
    popup = html`<${TradePopup} key=${game.trade ? 'counter' : 'new'} game=${game} me=${me}
      initial=${panel.initial} send=${send} onClose=${close} />`;
  } else if (game.trade && game.trade.from === me && tradeWindow) {
    popup = html`<${MyOfferPopup} game=${game} me=${me} send=${send} />`;
  } else if (panel?.kind === 'fish') {
    popup = html`<${FishPopup} game=${game} me=${me} send=${send} onClose=${close} />`;
  } else if (panel?.kind === 'deposit') {
    popup = html`<${DepositPopup} game=${game} me=${me} send=${send} onClose=${close} />`;
  }

  const roll = game.rolled && game.dice ? game.dice[0] + game.dice[1] : null;
  const myMove = myTurn || mine.length > 0 || (game.phase === 'setup' && game.setup.player === me)
    || Boolean(game.trade && game.trade.from !== me && tradeWindow);
  useEffect(() => {
    document.title = myMove && game.phase !== 'finished' ? '● Your move · Settlers' : 'Settlers';
    return () => { document.title = 'Settlers'; };
  }, [myMove, game.phase]);

  const devAffordable = canAfford(info.hand, game.costs.dev_card) && game.dev_deck > 0;

  return html`<div class="table">
    <${OpponentBar} game=${game} p=${1 - me} />
    <section class="board-area">
      <${Board} board=${board} roll=${roll} robber=${game.robber}>
        <${Pieces} board=${board} game=${game} />
        ${active && html`<${Targets} board=${board} kind=${TARGET_KIND[active]} ids=${targets}
          selected=${active === 'move_ship' ? shipFrom : robberHex} onPick=${onPick}
          classFor=${active === 'route' ? (id) => (roadSpots.has(id) ? (shipSpots.has(id) ? 'either' : '') : 'only-ship') : null} />`}
      <//>
      ${popup && html`<div class="popup-anchor" ...${popupDrag}>${popup}</div>`}
    </section>
    <${PlayerBar} game=${game} p=${me} onPlayDev=${playDev}
      onBank=${() => setPanel({ kind: 'deposit' })} onFish=${() => setPanel({ kind: 'fish' })}
      canFish=${mainPhase && info.fish.length > 0} />

    <aside class="side">
      <div class=${'prompt' + (myMove ? ' mine' : '')}>${promptText(game, me)}</div>
      <${Dice} dice=${game.dice} current=${game.rolled} />
      <div class="turn-buttons">
        ${myTurn && !game.rolled && html`<button class="primary big" disabled=${game.pending.length > 0}
          onClick=${() => send({ type: 'roll' })}>Roll dice</button>`}
        ${mainPhase && html`<button class="big" onClick=${() => send({ type: 'end_turn' })}>End turn</button>`}
      </div>
      ${routePlacing && html`<div class="coast-choice">
        <div class="muted small">Coastal spots (outlined in blue) take:</div>
        <div class="toggle">
          <button class=${coastKind === 'road' ? 'active' : ''} onClick=${() => setCoastKind('road')}>Road</button>
          <button class=${coastKind === 'ship' ? 'active' : ''} onClick=${() => setCoastKind('ship')}>Ship</button>
        </div>
        ${freeRoutes && html`<button onClick=${() => send({ type: 'skip_free_routes' })}>Skip the rest</button>`}
      </div>`}
      ${mainPhase && html`<div class="actions-panel">
        <${BuildButtons} game=${game} me=${me} mode=${active} setMode=${chooseMode}
          kinds=${['road', 'ship', 'settlement', 'city']} />
        <div class="build">
          <button class="build-btn" disabled=${!devAffordable} onClick=${() => send({ type: 'buy_dev' })}
            title=${`${game.dev_deck} left`}>
            <span>Dev card</span><${MiniCost} cost=${game.costs.dev_card} /></button>
          ${(legal.move_ship || []).length > 0 && html`<button
            class=${'build-btn' + (active === 'move_ship' ? ' active' : '')}
            onClick=${() => chooseMode(active === 'move_ship' ? null : 'move_ship')}>
            <span>Move ship</span><span class="muted small">${shipFrom == null ? 'pick a ship' : 'pick where'}</span>
          </button>`}
        </div>
        <div class="build">
          <button onClick=${() => setPanel({ kind: 'trade' })}>Trade…</button>
          <button disabled=${!info.fish.length} onClick=${() => setPanel({ kind: 'fish' })}>Spend fish…</button>
          ${game.can_pass_boot && html`<button onClick=${() => send({ type: 'pass_boot' })}>Pass the old boot</button>`}
        </div>
      </div>`}
      ${!mainPhase && tradeWindow && !game.trade && html`<div class="build">
        <button onClick=${() => setPanel({ kind: 'trade' })}>Propose a trade…</button>
      </div>`}
      <${Log} entries=${game.log} names=${game.names} />
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
