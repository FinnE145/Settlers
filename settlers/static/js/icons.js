// Small SVG pictures: resource cards, card backs, dice, VP token, pieces, fish.
import { h } from 'preact';
import htm from 'htm';

const html = htm.bind(h);

// Glyphs drawn in a 24x24 box.
const GLYPHS = {
  wood: html`<g>
    <polygon points="12,2 19,11 15.5,11 20,17 4,17 8.5,11 5,11" />
    <rect x="10.5" y="17" width="3" height="5" />
  </g>`,
  brick: html`<g>
    <rect x="2" y="4" width="9" height="5" /><rect x="13" y="4" width="9" height="5" />
    <rect x="7" y="11" width="10" height="5" /><rect x="2" y="18" width="9" height="4" />
    <rect x="13" y="18" width="9" height="4" />
  </g>`,
  sheep: html`<g>
    <circle cx="9" cy="12" r="4.5" /><circle cx="14" cy="11" r="4.5" /><circle cx="11" cy="15" r="4" />
    <circle cx="15" cy="15" r="3.5" /><ellipse cx="19.5" cy="10.5" rx="2.6" ry="2" class="g-dark" />
    <rect x="8" y="18" width="1.6" height="4" class="g-dark" /><rect x="14" y="18" width="1.6" height="4" class="g-dark" />
  </g>`,
  wheat: html`<g>
    <rect x="11.3" y="6" width="1.4" height="16" />
    ${[6, 9.5, 13].map((y) => html`<ellipse cx="9.3" cy=${y + 1} rx="1.7" ry="3" transform=${`rotate(-30 9.3 ${y + 1})`} />
      <ellipse cx="14.7" cy=${y + 1} rx="1.7" ry="3" transform=${`rotate(30 14.7 ${y + 1})`} />`)}
    <ellipse cx="12" cy="4" rx="1.6" ry="3" />
  </g>`,
  ore: html`<g>
    <polygon points="2,21 6,11 10,14 13,6 17,12 22,21" />
    <polygon points="13,6 15,15 17,12" class="g-dark" />
  </g>`,
};

export function ResGlyph({ res, size = 24, x = 0, y = 0 }) {
  return html`<svg x=${x} y=${y} width=${size} height=${size} viewBox="0 0 24 24" class=${'glyph g-' + res}>
    ${GLYPHS[res]}
  </svg>`;
}

/** One resource card, optionally with a count badge. */
export function ResCard({ res, count, w = 44, badge = true, dim = false }) {
  const hgt = Math.round(w * 1.4);
  const g = Math.round(w * 0.6);
  return html`<svg width=${w} height=${hgt} viewBox=${`0 0 ${w} ${hgt}`} class=${'card' + (dim ? ' dim' : '')}>
    <rect x="1" y="1" width=${w - 2} height=${hgt - 2} rx="5" class=${'card-face c-' + res} />
    <rect x="4" y="4" width=${w - 8} height=${hgt - 8} rx="3" class="card-inner" />
    <${ResGlyph} res=${res} size=${g} x=${(w - g) / 2} y=${(hgt - g) / 2} />
    ${badge && count != null && html`<g>
      <circle cx=${w - 9} cy="10" r="8" class="card-badge" />
      <text x=${w - 9} y="10.5" class="card-badge-text">${count}</text>
    </g>`}
  </svg>`;
}

/** A pile of identical cards with the count on top. */
export function CardStack({ res, n, w = 44 }) {
  const layers = Math.min(n, 4);
  const hgt = Math.round(w * 1.4);
  const off = 4;
  return html`<span class="stack" title=${`${n} ${res}`}
      style=${{ width: `${w + (layers - 1) * off}px`, height: `${hgt}px` }}>
    ${Array.from({ length: layers }, (_, i) => html`<span key=${i} class="stack-layer"
      style=${{ left: `${i * off}px` }}><${ResCard} res=${res} count=${n} w=${w} badge=${i === layers - 1} /></span>`)}
  </span>`;
}

export function CardBack({ w = 30 }) {
  const hgt = Math.round(w * 1.4);
  return html`<svg width=${w} height=${hgt} viewBox=${`0 0 ${w} ${hgt}`} class="card">
    <rect x="1" y="1" width=${w - 2} height=${hgt - 2} rx="4" class="card-back" />
    <rect x="3.5" y="3.5" width=${w - 7} height=${hgt - 7} rx="2.5" class="card-back-inner" />
    <polygon points=${hexagon(w / 2, hgt / 2, w * 0.22)} class="card-back-emblem" />
  </svg>`;
}

function hexagon(cx, cy, r) {
  return [0, 1, 2, 3, 4, 5].map((i) => {
    const a = (Math.PI / 3) * i - Math.PI / 2;
    return `${cx + r * Math.cos(a)},${cy + r * Math.sin(a)}`;
  }).join(' ');
}

/** A fanned cluster of card backs with a number over it. */
export function BackCluster({ n, w = 30, label }) {
  const shown = Math.min(Math.max(n, 1), 3);
  const hgt = Math.round(w * 1.4);
  return html`<span class=${'cluster' + (n === 0 ? ' empty' : '')} title=${label}
      style=${{ width: `${w + (shown - 1) * 7}px`, height: `${hgt}px` }}>
    ${Array.from({ length: shown }, (_, i) => html`<span key=${i} class="stack-layer"
      style=${{ left: `${i * 7}px`, transform: `rotate(${(i - (shown - 1) / 2) * 7}deg)` }}><${CardBack} w=${w} /></span>`)}
    <span class="cluster-n">${n}</span>
  </span>`;
}

const PIPS = {
  1: [[2, 2]], 2: [[1, 1], [3, 3]], 3: [[1, 1], [2, 2], [3, 3]],
  4: [[1, 1], [3, 1], [1, 3], [3, 3]], 5: [[1, 1], [3, 1], [2, 2], [1, 3], [3, 3]],
  6: [[1, 1], [3, 1], [1, 2], [3, 2], [1, 3], [3, 3]],
};

export function Die({ value, size = 40 }) {
  return html`<svg width=${size} height=${size} viewBox="0 0 40 40" class="die-svg">
    <rect x="1.5" y="1.5" width="37" height="37" rx="7" class="die-face" />
    ${PIPS[value].map(([c, r], i) => html`<circle key=${i} cx=${c * 10} cy=${r * 10} r="3.6" class="die-pip" />`)}
  </svg>`;
}

export function VPToken({ size = 34 }) {
  const c = size / 2;
  return html`<svg width=${size} height=${size} viewBox=${`0 0 ${size} ${size}`} class="vp-token">
    <circle cx=${c} cy=${c} r=${c - 1.5} class="vp-outer" />
    <circle cx=${c} cy=${c} r=${c - 5} class="vp-inner" />
    <polygon points=${star(c, c, c * 0.5, c * 0.22)} class="vp-star" />
  </svg>`;
}

function star(cx, cy, R, r) {
  const pts = [];
  for (let i = 0; i < 10; i++) {
    const rad = i % 2 ? r : R;
    const a = (Math.PI / 5) * i - Math.PI / 2;
    pts.push(`${cx + rad * Math.cos(a)},${cy + rad * Math.sin(a)}`);
  }
  return pts.join(' ');
}

const SETTLEMENT = 'M12 3 L20 10 L20 21 L4 21 L4 10 Z';
const CITY = 'M2 21 L2 10 L8 5 L14 10 L14 12 L22 12 L22 21 Z';

export function PieceIcon({ kind, colour, faded = false, size = 22 }) {
  return html`<svg width=${size} height=${size} viewBox="0 0 24 24"
      class=${`piece-icon p-${colour}${faded ? ' faded' : ''}`}>
    <path d=${kind === 'city' ? CITY : SETTLEMENT} />
  </svg>`;
}

export function FishToken({ value, size = 30 }) {
  return html`<svg width=${size} height=${size} viewBox="0 0 30 30" class="fish-token">
    <circle cx="15" cy="15" r="13.5" class="fish-bg" />
    <path d="M6 15 Q11 9 17 15 Q11 21 6 15 Z M17 15 L22 11 L22 19 Z" class="fish-glyph" />
    ${value != null && html`<text x="21.5" y="22.5" class="fish-n">${value}</text>`}
  </svg>`;
}

export function BootIcon({ size = 30 }) {
  return html`<svg width=${size} height=${size} viewBox="0 0 30 30" class="boot-icon">
    <title>Old boot: needs 1 more VP to win</title>
    <circle cx="15" cy="15" r="13.5" class="boot-bg" />
    <path d="M10 6 H17 V16 L23 18 Q25 19 24 22 H8 V18 Z" class="boot-glyph" />
  </svg>`;
}
