// The in-game screen: opponent bar, board, your bar, side panel and pop-ups.
import { h } from 'preact';
import { useEffect, useRef, useState } from 'preact/hooks';
import htm from 'htm';
import { Board, Pieces, Targets } from './board.js';
import { api } from './api.js';
import { NAMES, OpponentBar, PlayerBar } from './hud.js';
import { Die, ResGlyph } from './icons.js';
import {
  CardSelect, DepositPopup, FishPopup, MonopolyPopup, MyOfferPopup, OfferPopup, Popup,
  RobberPopup, TradePopup, YearOfPlentyPopup,
} from './popups.js';
import { LinkBox } from './ui.js';

const html = htm.bind(h);

const TARGET_KIND = {
  settlement: 'vertex', city: 'vertex', road: 'edge', ship: 'edge', robber: 'hex', pirate: 'hex',
  move_ship: 'edge', ship_target: 'edge',
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
  if (game.phase === 'finished') return game.winner === me ? 'You win!' : `${NAMES[game.winner]} wins.`;
  const discardsWaiting = game.pending.some((p) => p.type === 'discard');
  const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
  for (const p of game.pending.filter((q) => q.player === me)) {
    if (p.type === 'discard') return `Discard ${plural(p.count, 'card')}.`;
    if (p.type === 'gold') return `Pick ${plural(p.count, 'card')} from gold.`;
    if (p.type === 'robber') return discardsWaiting ? 'Waiting for discards…' : 'Move the robber or the pirate.';
    if (p.type === 'free_routes') return `Place ${plural(p.count, 'free road or ship')}.`;
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
  const [shipFrom, setShipFrom] = useState(null);
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

  // Forced placements pick their own mode; otherwise use what the player chose.
  let active = mode;
  if (game.phase === 'setup' && game.setup.player === me) {
    if (game.setup.awaiting === 'settlement') active = 'settlement';
    else if (mode !== 'road' && mode !== 'ship') active = (legal.road || []).length ? 'road' : 'ship';
  } else if (robberDue) {
    if (mode !== 'robber' && mode !== 'pirate') active = 'robber';
  } else if (active === 'move_ship') {
    if (!(legal.move_ship || []).length) active = null;
  } else if (active && !(legal[active] || []).length) {
    active = null;
  }
  // Ship moves pick a ship first, then where it goes.
  let targets = active && legal[active];
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
    if (BUILD_ACTION[active]) {
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
    popup = html`<${Popup} title=${game.winner === me ? 'You win!' : `${NAMES[game.winner]} wins`}>
      <div class="final">
        ${game.players.map((p, i) => html`<div key=${i} class=${'final-row name-' + p.colour}>
          <b>${NAMES[i]}</b> <span>${p.total_vp} VP</span>
          ${p.dev.some((d) => d.card === 'victory_point')
            && html`<span class="muted small">(incl. ${p.dev.filter((d) => d.card === 'victory_point').length} VP card)</span>`}
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
    popup = html`<${MyOfferPopup} game=${game} send=${send} />`;
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
          selected=${active === 'move_ship' ? shipFrom : robberHex} onPick=${onPick} />`}
      <//>
      ${popup && html`<div class="popup-anchor">${popup}</div>`}
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
      ${setupRoute && html`<${BuildButtons} game=${game} me=${me} mode=${active} setMode=${chooseMode}
        kinds=${['road', 'ship']} free />`}
      ${freeRoutes && html`<div>
        <${BuildButtons} game=${game} me=${me} mode=${active} setMode=${chooseMode} kinds=${['road', 'ship']} free />
        <button class="small-gap" onClick=${() => send({ type: 'skip_free_routes' })}>Skip the rest</button>
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
