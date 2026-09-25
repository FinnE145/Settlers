// The player areas around the board: opponent along the top, you along the bottom.
import { h } from 'preact';
import { useEffect, useRef, useState } from 'preact/hooks';
import htm from 'htm';
import { BackCluster, BootIcon, CardStack, DevCard, FishToken, PieceIcon, ResCard, VPToken } from './icons.js';
import { RESOURCES } from './ui.js';

const html = htm.bind(h);
export const COLOURS = ['red', 'blue'];
const SETTLEMENTS = 5;
const CITIES = 4;

function isActive(game, p) {
  if (game.phase === 'setup') return game.setup.player === p;
  return game.phase === 'play' && game.current === p;
}

/** Settlements and cities: solid for ones still in your supply, faded for placed ones. */
export function PieceSupply({ info, colour, size = 20 }) {
  const lifted = info.settlements >= SETTLEMENTS && info.cities >= CITIES;
  const row = (kind, placed, limit) => {
    const free = Math.max(limit - placed, 0);
    return html`<span class="supply-row" title=${`${placed} ${kind}${placed === 1 ? '' : 's'} placed`}>
      ${Array.from({ length: free }, (_, i) => html`<${PieceIcon} key=${'f' + i} kind=${kind} colour=${colour} size=${size} />`)}
      ${Array.from({ length: placed }, (_, i) => html`<${PieceIcon} key=${'p' + i} kind=${kind} colour=${colour} size=${size} faded />`)}
    </span>`;
  };
  return html`<span class="supply">
    ${row('settlement', info.settlements, SETTLEMENTS)}
    ${row('city', info.cities, CITIES)}
    ${lifted && html`<span class="unlimited" title="Limits lifted: build either freely">∞</span>`}
  </span>`;
}

const TITLES = [
  ['longest_route', 'Longest route', 'Longest trade route (1 VP)'],
  ['largest_army', 'Largest army', 'Largest army (1 VP)'],
  ['harbourmaster', 'Harbourmaster', 'Most harbours (1 VP)'],
  ['master_fisherman', 'Master fisherman', 'Most settlements and cities on fish (1 VP)'],
];

function Badges({ info }) {
  return html`<span class="badges">
    ${TITLES.filter(([key]) => info[key]).map(([key, label, title]) =>
      html`<span key=${key} class="badge" title=${title}>${label}</span>`)}
  </span>`;
}

function Stat({ label, value, title }) {
  return html`<span class="stat" title=${title}><span class="stat-label">${label}</span> <b>${value}</b></span>`;
}

/** Knights, route, harbours and fish buildings as a 2×2 grid. */
function Stats({ info, whose }) {
  return html`<div class="stat-grid">
    <${Stat} label="Knights" value=${info.knights} title="Knights played" />
    <${Stat} label="Route" value=${info.route_length} title="Longest trade route length" />
    <${Stat} label="Harbours" value=${info.harbours} title=${`Harbours with ${whose} settlements or cities`} />
    <${Stat} label="On fish" value=${info.fish_buildings} title="Settlements and cities on fish" />
  </div>`;
}

export function OpponentBar({ game, p }) {
  const info = game.players[p];
  const colour = COLOURS[p];
  return html`<div class=${`bar top pc-${colour}${isActive(game, p) ? ' active' : ''}`}>
    <div class="bar-id">
      <span class="bar-name"><span class=${'swatch p-' + colour}></span>
        <span class=${'name-' + colour}>${game.names[p]}</span></span>
      <${Badges} info=${info} />
    </div>
    <span class="group" title="Cards in hand"><${BackCluster} n=${info.hand_count} w=${30} label="Cards in hand" /></span>
    <span class="group small-group" title="Cards in bank">
      <${BackCluster} n=${info.bank_count} w=${20} label="Cards in bank" /><span class="group-label">bank</span>
    </span>
    <span class="group" title="Fish tokens"><${FishToken} size=${26} /><b>×${info.fish_count}</b></span>
    ${info.boot && html`<${BootIcon} size=${26} />`}
    <span class="group small-group" title="Development cards">
      <${BackCluster} n=${info.dev_count} w=${20} label="Development cards" dev /><span class="group-label">dev</span>
    </span>
    <${Stats} info=${info} whose="their" />
    <${PieceSupply} info=${info} colour=${colour} size=${16} />
    <span class="vp small" title="Victory points (public)">
      <${VPToken} size=${28} /><b>${info.vp}</b><span class="vp-of">/${info.vp_needed}</span>
    </span>
  </div>`;
}

/** Resources whose count just went up, for a moment. */
function useRecentGains(hand) {
  const prev = useRef(hand);
  const [gained, setGained] = useState([]);
  useEffect(() => {
    const up = RESOURCES.filter((r) => hand[r] > prev.current[r]);
    prev.current = hand;
    if (!up.length) return undefined;
    setGained(up);
    const t = setTimeout(() => setGained([]), 1800);
    return () => clearTimeout(t);
  }, [RESOURCES.map((r) => hand[r]).join()]);
  return gained;
}

/** Your development cards, grouped; playable ones are buttons. */
function DevCards({ dev, playable, onPlay }) {
  if (!dev.length) return null;
  const groups = {};
  for (const d of dev) {
    const key = d.card + (d.new ? ':new' : '');
    groups[key] = groups[key] || { card: d.card, isNew: d.new, n: 0 };
    groups[key].n += 1;
  }
  return html`<div class="dev-cards">
    ${Object.entries(groups).map(([key, g]) => {
      const can = (!g.isNew || g.card === 'victory_point') && playable.includes(g.card);
      const title = can ? 'Click to play'
        : g.isNew && g.card !== 'victory_point' ? 'Got this turn: playable from next turn' : 'Not playable right now';
      return html`<button key=${key} class=${'card-btn dev' + (g.isNew ? ' new' : '')} disabled=${!can}
        title=${title} onClick=${() => onPlay(g.card)}>
        <${DevCard} card=${g.card} count=${g.n} dim=${g.isNew && g.card !== 'victory_point'} w=${36} />
      </button>`;
    })}
  </div>`;
}

export function PlayerBar({ game, p, onPlayDev, onBank, onFish, canFish }) {
  const info = game.players[p];
  const colour = COLOURS[p];
  const gained = useRecentGains(info.hand);
  const held = RESOURCES.filter((r) => info.hand[r] > 0);
  const banked = RESOURCES.filter((r) => info.bank[r] > 0);
  const canBank = game.phase === 'play' && game.pending.length === 0 && info.hand_count > 0;
  return html`<div class=${`bar bottom pc-${colour}${isActive(game, p) ? ' active' : ''}`}>
    <div class="hand">
      ${held.length
        ? held.map((r) => html`<span key=${r} class=${gained.includes(r) ? 'gained' : ''}>
            <${CardStack} res=${r} n=${info.hand[r]} w=${40} /></span>`)
        : html`<span class="muted">No cards in hand</span>`}
    </div>
    <${DevCards} dev=${info.dev} playable=${game.playable_dev} onPlay=${onPlayDev} />
    <button class="bank area-btn" disabled=${!canBank} onClick=${onBank}
        title="Your bank: click to put cards in (your opponent only sees the count)">
      <div class="group-label">Bank</div>
      <div class="bank-cards">
        ${banked.length
          ? banked.map((r) => html`<${ResCard} key=${r} res=${r} count=${info.bank[r]} w=${24} />`)
          : html`<span class="muted small">empty</span>`}
      </div>
    </button>
    <button class="fish area-btn" disabled=${!canFish} onClick=${onFish}
        title="Your fish tokens: click to spend them on your turn">
      ${info.fish.length
        ? info.fish.map((v, i) => html`<${FishToken} key=${i} value=${v} size=${28} />`)
        : html`<span class="muted small">No fish</span>`}
      ${info.boot && html`<${BootIcon} size=${28} />`}
    </button>
    <div class="mine-stats">
      <${Stats} info=${info} whose="your" />
      <${Badges} info=${info} />
    </div>
    <div class="score">
      <span class="vp" title="Victory points">
        <${VPToken} size=${40} /><b>${info.vp}</b><span class="vp-of">/${info.vp_needed}</span>
      </span>
      <${PieceSupply} info=${info} colour=${colour} size=${18} />
    </div>
  </div>`;
}
