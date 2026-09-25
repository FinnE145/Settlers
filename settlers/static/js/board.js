// SVG rendering of the board: terrain, numbers, harbours and fisheries.
import { h } from 'preact';
import htm from 'htm';

const html = htm.bind(h);

export const HEX_R = 40; // hex radius in px
const XU = (HEX_R * Math.sqrt(3)) / 2; // one grid X unit (half a hex width)
const YU = HEX_R / 2; // one grid Y unit
const CORNERS = [[0, -2], [1, -1], [1, 1], [0, 2], [-1, 1], [-1, -1]];

export const px = (x) => x * XU;
export const py = (y) => y * YU;

export const TERRAIN = {
  forest: { label: 'Forest', pattern: 'pat-forest' },
  hills: { label: 'Hills', pattern: 'pat-hills' },
  pasture: { label: 'Pasture', pattern: 'pat-pasture' },
  fields: { label: 'Fields', pattern: 'pat-fields' },
  mountains: { label: 'Mountains', pattern: 'pat-mountains' },
  gold: { label: 'Gold field', pattern: 'pat-gold' },
  lake: { label: 'Lake', pattern: 'pat-fishery' },
  sea: { label: 'Sea', pattern: 'pat-sea' },
};

export const RESOURCE_TERRAIN = {
  wood: 'forest', brick: 'hills', sheep: 'pasture', wheat: 'fields', ore: 'mountains',
};

function hexPoints(hx) {
  return CORNERS.map(([dx, dy]) => `${px(hx.x + dx)},${py(hx.y + dy)}`).join(' ');
}

function cornerPoint(hx, i) {
  const [dx, dy] = CORNERS[((i % 6) + 6) % 6];
  return [px(hx.x + dx), py(hx.y + dy)];
}

function lerp([ax, ay], [bx, by], t) {
  return [ax + (bx - ax) * t, ay + (by - ay) * t];
}

function Patterns() {
  return html`<defs>
    <pattern id="pat-forest" width="16" height="16" patternUnits="userSpaceOnUse">
      <polygon points="8,2 13,12 3,12" class="p-forest" />
    </pattern>
    <pattern id="pat-pasture" width="14" height="14" patternUnits="userSpaceOnUse">
      <circle cx="7" cy="7" r="2.4" class="p-pasture" />
    </pattern>
    <pattern id="pat-fields" width="10" height="10" patternUnits="userSpaceOnUse">
      <path d="M0 10 L10 0" class="p-fields" />
    </pattern>
    <pattern id="pat-hills" width="16" height="10" patternUnits="userSpaceOnUse">
      <path d="M0 0.5 H16 M0 5.5 H16 M0.5 0 V5 M8.5 5 V10" class="p-hills" />
    </pattern>
    <pattern id="pat-mountains" width="20" height="14" patternUnits="userSpaceOnUse">
      <polygon points="10,2 18,13 2,13" class="p-mountains" />
      <polygon points="10,2 12.4,5.3 7.6,5.3" class="p-snow" />
    </pattern>
    <pattern id="pat-gold" width="14" height="14" patternUnits="userSpaceOnUse">
      <polygon points="7,3 10,7 7,11 4,7" class="p-gold" />
    </pattern>
    <pattern id="pat-sea" width="24" height="16" patternUnits="userSpaceOnUse">
      <path d="M0 8 Q6 5 12 8 T24 8" class="p-sea" />
    </pattern>
    <pattern id="pat-fishery" width="14" height="10" patternUnits="userSpaceOnUse">
      <path d="M2 5 Q6 2 9 5 Q6 8 2 5 Z M9 5 L12 3 L12 7 Z" class="p-fish" />
    </pattern>
  </defs>`;
}

export function NumberToken({ x, y, n, r = 14 }) {
  const red = n === 6 || n === 8;
  const pips = 6 - Math.abs(7 - n);
  const dots = [];
  for (let i = 0; i < pips; i++) {
    dots.push(html`<circle cx=${x + (i - (pips - 1) / 2) * 3.4} cy=${y + r * 0.55} r="1.2"
      class=${red ? 'pip red' : 'pip'} />`);
  }
  return html`<g class="token">
    <circle cx=${x} cy=${y} r=${r} class="token-bg" />
    <text x=${x} y=${y - 1} class=${red ? 'token-num red' : 'token-num'}>${n}</text>
    ${dots}
  </g>`;
}

function LakeToken({ x, y, numbers }) {
  const half = Math.ceil(numbers.length / 2);
  return html`<g class="token">
    <circle cx=${x} cy=${y} r="15" class="token-bg" />
    <text x=${x} y=${y - 4} class="token-small">${numbers.slice(0, half).join(' ')}</text>
    <text x=${x} y=${y + 6} class="token-small">${numbers.slice(half).join(' ')}</text>
  </g>`;
}

function Harbour({ harbour, board }) {
  const edge = board.edges[harbour.edge];
  const [a, b] = edge.v.map((vid) => [px(board.vertices[vid].x), py(board.vertices[vid].y)]);
  const sea = board.hexes[harbour.sea];
  const mid = lerp(a, b, 0.5);
  const [x, y] = lerp(mid, [px(sea.x), py(sea.y)], 0.55);
  const generic = harbour.kind === '3:1';
  const ring = generic ? 'harbour-ring generic' : `harbour-ring t-${RESOURCE_TERRAIN[harbour.kind]}`;
  return html`<g class="harbour">
    <title>${generic ? '3:1 harbour' : `2:1 ${harbour.kind} harbour`}</title>
    <line x1=${a[0]} y1=${a[1]} x2=${x} y2=${y} class="dock" />
    <line x1=${b[0]} y1=${b[1]} x2=${x} y2=${y} class="dock" />
    <circle cx=${x} cy=${y} r="13" class=${ring} />
    <text x=${x} y=${generic ? y : y - 2} class="harbour-text">${generic ? '3:1' : '2:1'}</text>
    ${!generic && html`<text x=${x} y=${y + 7} class="harbour-res">${harbour.kind}</text>`}
  </g>`;
}

function Fishery({ fishery, board }) {
  const hx = board.hexes[fishery.hex];
  const points = fisheryPoints(board, fishery);
  const [tx, ty] = lerp([px(hx.x), py(hx.y)], cornerPoint(hx, fishery.corner), 0.3);
  return html`<g class="fishery">
    <title>Fishing ground ${fishery.number}</title>
    <polygon points=${points} class="fishery-band" />
    <polygon points=${points} fill="url(#pat-fishery)" class="overlay" />
    <${NumberToken} x=${tx} y=${ty} n=${fishery.number} r="11" />
  </g>`;
}

function boardBounds(board) {
  const inner = board.hexes.filter((hx) => !hx.frame);
  const xs = inner.flatMap((hx) => [px(hx.x - 1), px(hx.x + 1)]);
  const ys = inner.flatMap((hx) => [py(hx.y - 2), py(hx.y + 2)]);
  const m = HEX_R * 1.3;
  const minX = Math.min(...xs) - m;
  const minY = Math.min(...ys) - m;
  return [minX, minY, Math.max(...xs) + m - minX, Math.max(...ys) + m - minY];
}

// ------------------------------------------------------------------ pieces

const vpos = (board, vid) => [px(board.vertices[vid].x), py(board.vertices[vid].y)];
const hpos = (board, hid) => [px(board.hexes[hid].x), py(board.hexes[hid].y)];
export const COLOURS = ['red', 'blue'];

function edgeEnds(board, eid, trim = 0) {
  const [a, b] = board.edges[eid].v.map((vid) => vpos(board, vid));
  return [lerp(a, b, trim), lerp(a, b, 1 - trim)];
}

function shipPoints(board, eid) {
  const [a, b] = edgeEnds(board, eid);
  const len = Math.hypot(b[0] - a[0], b[1] - a[1]);
  const u = [(b[0] - a[0]) / len, (b[1] - a[1]) / len];
  const n = [-u[1], u[0]];
  const m = lerp(a, b, 0.5);
  const L = len * 0.62;
  const W = 9;
  const pt = (s, t) => [m[0] + u[0] * s + n[0] * t, m[1] + u[1] * s + n[1] * t];
  return [pt(L / 2, 0), pt(L / 4, W / 2), pt(-L / 4, W / 2), pt(-L / 2, 0), pt(-L / 4, -W / 2), pt(L / 4, -W / 2)]
    .map((p) => p.join(',')).join(' ');
}

const SETTLEMENT = [[0, -10], [8, -3], [8, 8], [-8, 8], [-8, -3]];
const CITY = [[-11, 10], [11, 10], [11, -2], [2, -2], [2, -8], [-4.5, -14], [-11, -8]];
const shape = (pts, [x, y]) => pts.map(([dx, dy]) => `${x + dx},${y + dy}`).join(' ');

export function Pieces({ board, game }) {
  const routes = game.routes.map((r) => {
    const colour = COLOURS[r.owner];
    if (r.kind === 'road') {
      const [a, b] = edgeEnds(board, r.edge, 0.12);
      return html`<g key=${'r' + r.edge}>
        <line x1=${a[0]} y1=${a[1]} x2=${b[0]} y2=${b[1]} class="road-outline" />
        <line x1=${a[0]} y1=${a[1]} x2=${b[0]} y2=${b[1]} class=${'road p-' + colour} />
      </g>`;
    }
    const m = lerp(...edgeEnds(board, r.edge), 0.5);
    return html`<g key=${'s' + r.edge}>
      <polygon points=${shipPoints(board, r.edge)} class=${'ship p-' + colour} />
      <circle cx=${m[0]} cy=${m[1]} r="2" class="mast" />
    </g>`;
  });
  const buildings = game.buildings.map((b) => html`<polygon key=${'b' + b.vertex}
    points=${shape(b.kind === 'city' ? CITY : SETTLEMENT, vpos(board, b.vertex))}
    class=${'building p-' + COLOURS[b.owner]} />`);
  return html`<g class="pieces">
    ${routes}
    ${buildings}
    ${game.robber != null && html`<${Robber} pos=${hpos(board, game.robber)} />`}
    ${game.pirate != null && html`<${Pirate} pos=${hpos(board, game.pirate)} />`}
  </g>`;
}

function Robber({ pos: [x, y] }) {
  const cx = x - 22;
  return html`<g class="robber"><title>Robber</title>
    <path d=${`M${cx - 7} ${y + 12} L${cx - 4} ${y - 2} L${cx + 4} ${y - 2} L${cx + 7} ${y + 12} Z`} />
    <circle cx=${cx} cy=${y - 7} r="6" />
  </g>`;
}

function Pirate({ pos: [x, y] }) {
  const cx = x + 20;
  return html`<g class="pirate"><title>Pirate</title>
    <path d=${`M${cx - 12} ${y + 2} L${cx + 12} ${y + 2} L${cx + 8} ${y + 9} L${cx - 8} ${y + 9} Z`} />
    <path d=${`M${cx} ${y + 1} L${cx} ${y - 16} L${cx + 10} ${y - 4} Z`} />
  </g>`;
}

// ---------------------------------------------------------------- targets

/** A thin rectangle along an edge, used as its click target. */
function edgeBox(board, eid, halfWidth = 6) {
  const [a, b] = edgeEnds(board, eid, 0.18);
  const len = Math.hypot(b[0] - a[0], b[1] - a[1]);
  const n = [-(b[1] - a[1]) / len * halfWidth, (b[0] - a[0]) / len * halfWidth];
  return [[a[0] + n[0], a[1] + n[1]], [b[0] + n[0], b[1] + n[1]],
    [b[0] - n[0], b[1] - n[1]], [a[0] - n[0], a[1] - n[1]]].map((p) => p.join(',')).join(' ');
}

/** Clickable highlights: kind is 'vertex', 'edge' or 'hex'. */
export function Targets({ board, kind, ids, selected, onPick, classFor = null }) {
  if (!ids || !ids.length) return null;
  return html`<g class="targets">
    ${ids.map((id) => {
      const extra = classFor ? classFor(id) : '';
      const cls = 'target' + (id === selected ? ' selected' : '') + (extra ? ' ' + extra : '');
      const pick = () => onPick(id);
      if (kind === 'vertex') {
        const [x, y] = vpos(board, id);
        return html`<circle key=${id} cx=${x} cy=${y} r="9" class=${cls} onClick=${pick} />`;
      }
      if (kind === 'edge') {
        return html`<polygon key=${id} points=${edgeBox(board, id)} class=${cls + ' edge'} onClick=${pick} />`;
      }
      return html`<polygon key=${id} points=${hexPoints(board.hexes[id])} class=${cls + ' hex-target'}
        onClick=${pick} />`;
    })}
  </g>`;
}

/** Hexes (and fisheries) that produce on ``roll``. */
function rolledParts(board, roll) {
  if (!roll || roll === 7) return { hexes: [], fisheries: [] };
  const hexes = board.hexes.filter((hx) => board.numbers[hx.id] === roll
    || (board.terrain[hx.id] === 'lake' && board.lake_numbers.includes(roll))).map((hx) => hx.id);
  const fisheries = board.fisheries.filter((f) => f.number === roll);
  return { hexes, fisheries };
}

function RolledHighlight({ board, roll, robber }) {
  const { hexes, fisheries } = rolledParts(board, roll);
  return html`<g class="rolled-layer">
    ${hexes.map((id) => html`<polygon key=${'rh' + id} points=${hexPoints(board.hexes[id])}
      class=${id === robber ? 'rolled blocked' : 'rolled'} />`)}
    ${fisheries.map((f) => html`<polygon key=${'rf' + f.hex} points=${fisheryPoints(board, f)} class="rolled" />`)}
  </g>`;
}

function fisheryPoints(board, fishery) {
  const hx = board.hexes[fishery.hex];
  const c = [px(hx.x), py(hx.y)];
  const k = fishery.corner;
  const outer = [k - 1, k, k + 1].map((i) => cornerPoint(hx, i));
  const inner = outer.map((p) => lerp(c, p, 0.55)).reverse();
  return [...outer, ...inner].map((p) => p.join(',')).join(' ');
}

export function Board({ board, roll = null, robber = null, children }) {
  const [vx, vy, vw, vh] = boardBounds(board);
  return html`<svg class="board" viewBox="${vx} ${vy} ${vw} ${vh}" xmlns="http://www.w3.org/2000/svg">
    <${Patterns} />
    <rect x=${vx} y=${vy} width=${vw} height=${vh} class="frame-bg" />
    ${board.hexes.map((hx) => {
      const kind = board.terrain[hx.id];
      const t = TERRAIN[kind];
      const pts = hexPoints(hx);
      const cls = hx.frame ? 'hex frame' : `hex t-${kind}`;
      return html`<g key=${hx.id}>
        <title>${hx.frame ? 'Sea' : t.label}</title>
        <polygon points=${pts} class=${cls} />
        ${!hx.frame && html`<polygon points=${pts} fill="url(#${t.pattern})" class="overlay" />`}
      </g>`;
    })}
    ${board.fisheries.map((f) => html`<${Fishery} key=${'f' + f.hex} fishery=${f} board=${board} />`)}
    ${board.harbours.map((hb) => html`<${Harbour} key=${'h' + hb.edge} harbour=${hb} board=${board} />`)}
    <${RolledHighlight} board=${board} roll=${roll} robber=${robber} />
    ${board.hexes.map((hx) => {
      const n = board.numbers[hx.id];
      if (n != null) return html`<${NumberToken} key=${'n' + hx.id} x=${px(hx.x)} y=${py(hx.y)} n=${n} />`;
      if (board.terrain[hx.id] === 'lake') {
        return html`<${LakeToken} key="lake" x=${px(hx.x)} y=${py(hx.y)} numbers=${board.lake_numbers} />`;
      }
      return null;
    })}
    ${children}
  </svg>`;
}
