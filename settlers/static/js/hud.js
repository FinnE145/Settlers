// The player areas around the board: opponent along the top, you along the bottom.
import { h } from 'preact';
import { useEffect, useRef, useState } from 'preact/hooks';
import htm from 'htm';
import { BackCluster, BootIcon, CardStack, FishToken, PieceIcon, ResCard, VPToken } from './icons.js';
import { RESOURCES } from './ui.js';

const html = htm.bind(h);
export const NAMES = ['Red', 'Blue'];
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

function Badges({ info }) {
  return html`<span class="badges">
    ${info.longest_route && html`<span class="badge" title="Longest trade route (2 VP)">Longest route</span>`}
    ${info.largest_army && html`<span class="badge" title="Largest army (2 VP)">Largest army</span>`}
  </span>`;
}

function Stat({ label, value, title }) {
  return html`<span class="stat" title=${title}><span class="stat-label">${label}</span> <b>${value}</b></span>`;
}

export function OpponentBar({ game, p }) {
  const info = game.players[p];
  const colour = COLOURS[p];
  return html`<div class=${`bar top pc-${colour}${isActive(game, p) ? ' active' : ''}`}>
    <span class="bar-name"><span class=${'swatch p-' + colour}></span>${NAMES[p]}</span>
    <span class="group" title="Cards in hand"><${BackCluster} n=${info.hand_count} w=${30} label="Cards in hand" /></span>
    <span class="group small-group" title="Cards in bank">
      <${BackCluster} n=${info.bank_count} w=${20} label="Cards in bank" /><span class="group-label">bank</span>
    </span>
    <span class="group" title="Fish tokens"><${FishToken} size=${26} /><b>×${info.fish_count}</b></span>
    ${info.boot && html`<${BootIcon} size=${26} />`}
    <${Stat} label="Dev" value=${info.dev_count} title="Development cards in hand" />
    <${Stat} label="Knights" value=${info.knights} title="Knights played" />
    <${Stat} label="Route" value=${info.route_length} title="Longest trade route length" />
    <${Badges} info=${info} />
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

export function PlayerBar({ game, p }) {
  const info = game.players[p];
  const colour = COLOURS[p];
  const gained = useRecentGains(info.hand);
  const held = RESOURCES.filter((r) => info.hand[r] > 0);
  const banked = RESOURCES.filter((r) => info.bank[r] > 0);
  return html`<div class=${`bar bottom pc-${colour}${isActive(game, p) ? ' active' : ''}`}>
    <div class="hand">
      ${held.length
        ? held.map((r) => html`<span key=${r} class=${gained.includes(r) ? 'gained' : ''}>
            <${CardStack} res=${r} n=${info.hand[r]} /></span>`)
        : html`<span class="muted">No cards in hand</span>`}
    </div>
    <div class="bank" title="Your bank (only the count is visible to your opponent)">
      <div class="group-label">Bank</div>
      <div class="bank-cards">
        ${banked.length
          ? banked.map((r) => html`<${ResCard} key=${r} res=${r} count=${info.bank[r]} w=${24} />`)
          : html`<span class="muted small">empty</span>`}
      </div>
    </div>
    <div class="fish" title="Your fish tokens">
      ${info.fish.length
        ? info.fish.map((v, i) => html`<${FishToken} key=${i} value=${v} size=${28} />`)
        : html`<span class="muted small">No fish</span>`}
      ${info.boot && html`<${BootIcon} size=${28} />`}
    </div>
    <div class="mine-stats">
      <${Stat} label="Knights" value=${info.knights} />
      <${Stat} label="Route" value=${info.route_length} />
      <${Badges} info=${info} />
    </div>
    <${PieceSupply} info=${info} colour=${colour} />
    <span class="vp" title=${info.total_vp !== info.vp ? `${info.vp} public + ${info.total_vp - info.vp} hidden` : 'Victory points'}>
      <${VPToken} size=${40} /><b>${info.total_vp}</b><span class="vp-of">/${info.vp_needed}</span>
    </span>
  </div>`;
}
