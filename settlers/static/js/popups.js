// Pop-ups shown above your hand: choices, trades, the fish shop and the card bank.
import { h } from 'preact';
import { useState } from 'preact/hooks';
import htm from 'htm';
import { FishToken, ResCard } from './icons.js';
import { RESOURCES, emptyCards, total } from './ui.js';

const html = htm.bind(h);

export function Popup({ title, onClose, children, wide = false }) {
  return html`<div class=${'popup' + (wide ? ' wide' : '')}>
    <div class="popup-head">
      <span class="popup-title">${title}</span>
      ${onClose && html`<button class="close" title="Close" onClick=${onClose}>×</button>`}
    </div>
    ${children}
  </div>`;
}

/** Click a card to add one; the − under it takes one back. Controlled. */
export function CardPicker({ value, onChange, available = null, max = Infinity }) {
  const sum = total(value);
  return html`<div class="select-row">
    ${RESOURCES.map((r) => {
      const left = available ? available[r] - value[r] : Infinity;
      const can = sum < max && left > 0;
      return html`<div key=${r} class="select-card">
        <button class="card-btn" disabled=${!can} onClick=${() => onChange({ ...value, [r]: value[r] + 1 })}>
          <${ResCard} res=${r} count=${available ? available[r] : null} dim=${available && available[r] === 0} />
        </button>
        <div class="select-count">
          ${value[r] > 0
            ? html`<button class="small" onClick=${() => onChange({ ...value, [r]: value[r] - 1 })}>−</button>
                <b>${value[r]}</b>`
            : html`<span class="muted">·</span>`}
        </div>
      </div>`;
    })}
  </div>`;
}

/** Pick exactly ``count`` cards (or at least one when ``count`` is null), then submit. */
export function CardSelect({ count = null, available = null, onSubmit, label }) {
  const [value, setValue] = useState(emptyCards());
  const sum = total(value);
  const ok = count == null ? sum > 0 : sum === count;
  return html`<div>
    <${CardPicker} value=${value} onChange=${setValue} available=${available} max=${count ?? Infinity} />
    <div class="popup-actions">
      <span class="muted">${count == null ? `${sum} selected` : `${sum} / ${count}`}</span>
      <button class="primary" disabled=${!ok} onClick=${() => onSubmit(value)}>${label}</button>
    </div>
  </div>`;
}

// ------------------------------------------------------------- robber

function victimAt(board, game, piece, hex, me) {
  const o = 1 - me;
  if (piece === 'robber') {
    return board.hexes[hex].corners.some((v) => game.buildings.some((b) => b.vertex === v && b.owner === o));
  }
  return board.hexes[hex].edges.some((e) =>
    game.routes.some((r) => r.edge === e && r.owner === o && r.kind === 'ship'));
}

export function RobberPopup({ board, game, me, piece, setPiece, hex, send }) {
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
            Steal a random card from ${game.names[1 - me]} (${oppCards})</button>`}
          <div class="muted small-gap">${victim ? 'or take' : 'Take'} one from the supply:</div>
          <div class="select-row">
            ${RESOURCES.map((r) => html`<button key=${r} class="card-btn" onClick=${() => move(r)}>
              <${ResCard} res=${r} badge=${false} /></button>`)}
          </div>
        </div>`}
  <//>`;
}

// ------------------------------------------------------------- trading

function FishRequest({ value, onChange }) {
  return html`<div class="fish-request">
    ${[1, 2, 3].map((v) => html`<span key=${v} class="fish-req">
      <${FishToken} value=${v} size=${28} />
      <button class="small" disabled=${!value[v]} onClick=${() => onChange({ ...value, [v]: value[v] - 1 })}>−</button>
      <b>${value[v]}</b>
      <button class="small" onClick=${() => onChange({ ...value, [v]: value[v] + 1 })}>+</button>
    </span>`)}
  </div>`;
}

/** Toggle which of your own tokens are included. ``chosen`` is a list of indices. */
function FishChooser({ fish, chosen, onChange }) {
  if (!fish.length) return html`<span class="muted small">No fish</span>`;
  return html`<div class="fish-choose">
    ${fish.map((v, i) => html`<button key=${i} class=${'token-btn' + (chosen.includes(i) ? ' on' : '')}
      onClick=${() => onChange(chosen.includes(i) ? chosen.filter((j) => j !== i) : [...chosen, i])}>
      <${FishToken} value=${v} size=${30} /></button>`)}
  </div>`;
}

const fishList = (counts) => [1, 2, 3].flatMap((v) => Array(counts[v]).fill(v));
const fishCounts = (list) => ({ 1: 0, 2: 0, 3: 0, ...Object.fromEntries([1, 2, 3].map((v) => [v, list.filter((t) => t === v).length])) });

/** Pick token indices from ``fish`` matching the values in ``wanted`` where possible. */
function indicesFor(fish, wanted) {
  const used = [];
  for (const v of wanted) {
    const i = fish.findIndex((t, j) => t === v && !used.includes(j));
    if (i >= 0) used.push(i);
  }
  return used;
}

function PlayerTrade({ game, me, initial, send, onClose }) {
  const mine = game.players[me];
  const [give, setGive] = useState(initial ? { ...initial.get } : emptyCards());
  const [get, setGet] = useState(initial ? { ...initial.give } : emptyCards());
  const [giveFish, setGiveFish] = useState(initial ? indicesFor(mine.fish, initial.get_fish) : []);
  const [getFish, setGetFish] = useState(fishCounts(initial ? initial.give_fish : []));
  const giveOk = total(give) > 0 || giveFish.length > 0;
  const getOk = total(get) > 0 || fishList(getFish).length > 0;
  const offer = () => send({
    type: 'offer_trade', give, get,
    give_fish: giveFish.map((i) => mine.fish[i]), get_fish: fishList(getFish),
  }).then((ok) => ok && onClose());
  return html`<div class="trade">
    <div class="trade-side">
      <div class="trade-label">You give</div>
      <${CardPicker} value=${give} onChange=${setGive} available=${mine.hand} />
      <${FishChooser} fish=${mine.fish} chosen=${giveFish} onChange=${setGiveFish} />
    </div>
    <div class="trade-side">
      <div class="trade-label">You want from ${game.names[1 - me]}</div>
      <${CardPicker} value=${get} onChange=${setGet} />
      <${FishRequest} value=${getFish} onChange=${setGetFish} />
    </div>
    <div class="popup-actions">
      <button class="primary" disabled=${!giveOk || !getOk} onClick=${offer}>Offer to ${game.names[1 - me]}</button>
    </div>
  </div>`;
}

function BankTrade({ game, me, send }) {
  const hand = game.players[me].hand;
  const [give, setGive] = useState(null);
  const [get, setGet] = useState(null);
  const rate = give && get ? game.rates[give][get] : null;
  return html`<div class="trade">
    <div class="trade-label">Give</div>
    <div class="select-row">
      ${RESOURCES.map((r) => html`<button key=${r} class=${'card-btn pick' + (give === r ? ' on' : '')}
        onClick=${() => { setGive(r); if (get === r) setGet(null); }}>
        <${ResCard} res=${r} count=${hand[r]} dim=${hand[r] === 0} /></button>`)}
    </div>
    <div class="trade-label">Get</div>
    <div class="select-row">
      ${RESOURCES.map((r) => html`<div key=${r} class="select-card">
        <button class=${'card-btn pick' + (get === r ? ' on' : '')} disabled=${r === give}
          onClick=${() => setGet(r)}><${ResCard} res=${r} badge=${false} dim=${r === give} /></button>
        <span class="rate">${give && r !== give ? `${game.rates[give][r]}:1` : ''}</span>
      </div>`)}
    </div>
    <div class="popup-actions">
      <button class="primary" disabled=${!rate || hand[give] < rate}
        onClick=${() => send({ type: 'maritime', give, get })}>
        ${rate ? `Trade ${rate} ${give} for 1 ${get}` : 'Pick what to give and get'}
      </button>
    </div>
  </div>`;
}

export function TradePopup({ game, me, initial, send, onClose }) {
  const [tab, setTab] = useState('player');
  const canUseSupply = game.current === me;
  return html`<${Popup} title="Trade" onClose=${onClose} wide>
    <div class="toggle">
      <button class=${tab === 'player' ? 'active' : ''} onClick=${() => setTab('player')}>With ${game.names[1 - me]}</button>
      ${canUseSupply && html`<button class=${tab === 'bank' ? 'active' : ''} onClick=${() => setTab('bank')}>
        With the supply</button>`}
    </div>
    ${tab === 'player' || !canUseSupply
      ? html`<${PlayerTrade} game=${game} me=${me} initial=${initial} send=${send} onClose=${onClose} />`
      : html`<${BankTrade} game=${game} me=${me} send=${send} />`}
  <//>`;
}

function Side({ cards, fish }) {
  const shown = RESOURCES.filter((r) => cards[r] > 0);
  return html`<span class="offer-side">
    ${shown.map((r) => html`<span key=${r} class="offer-card"><${ResCard} res=${r} count=${cards[r]} w=${34} /></span>`)}
    ${fish.map((v, i) => html`<${FishToken} key=${'f' + i} value=${v} size=${28} />`)}
    ${!shown.length && !fish.length && html`<span class="muted">nothing</span>`}
  </span>`;
}

export function OfferPopup({ game, me, send, onCounter }) {
  const t = game.trade;
  const mine = game.players[me];
  const haveCards = RESOURCES.every((r) => mine.hand[r] >= t.get[r]);
  const counts = fishCounts(mine.fish);
  const need = fishCounts(t.get_fish);
  const haveFish = [1, 2, 3].every((v) => counts[v] >= need[v]);
  return html`<${Popup} title=${`${game.names[t.from]} offers a trade`}>
    <div class="offer-row"><span class="trade-label">You get</span><${Side} cards=${t.give} fish=${t.give_fish} /></div>
    <div class="offer-row"><span class="trade-label">You give</span><${Side} cards=${t.get} fish=${t.get_fish} /></div>
    ${!(haveCards && haveFish) && html`<div class="muted">You don't have what they're asking for.</div>`}
    <div class="popup-actions">
      <button onClick=${() => send({ type: 'decline_trade' })}>Decline</button>
      <button onClick=${() => onCounter(t)}>Counter…</button>
      <button class="primary" disabled=${!(haveCards && haveFish)} onClick=${() => send({ type: 'accept_trade' })}>Accept</button>
    </div>
  <//>`;
}

export function MyOfferPopup({ game, send }) {
  const t = game.trade;
  return html`<${Popup} title=${`Waiting for ${game.names[1 - t.from]}…`}>
    <div class="offer-row"><span class="trade-label">You give</span><${Side} cards=${t.give} fish=${t.give_fish} /></div>
    <div class="offer-row"><span class="trade-label">You get</span><${Side} cards=${t.get} fish=${t.get_fish} /></div>
    <div class="popup-actions"><button onClick=${() => send({ type: 'cancel_trade' })}>Withdraw offer</button></div>
  <//>`;
}

// ---------------------------------------------------------------- fish

const FISH_ITEMS = [
  { kind: 'bank', label: 'Empty your bank', max: (g, me) => (g.players[me].bank_count > 0 ? 1 : 0) },
  { kind: 'remove_robber', label: 'Remove the robber', max: (g) => (g.robber != null ? 1 : 0) },
  { kind: 'remove_pirate', label: 'Remove the pirate', max: (g) => (g.pirate != null ? 1 : 0) },
  { kind: 'steal', label: 'Steal a random card', max: (g, me) => g.players[1 - me].hand_count },
  { kind: 'route', label: 'Free road or ship', max: () => 9 },
  { kind: 'dev_card', label: 'Development card', max: (g) => g.dev_deck },
];

export function FishPopup({ game, me, send, onClose }) {
  const fish = game.players[me].fish;
  const prices = game.fish_prices;
  const [chosen, setChosen] = useState([]);
  const [counts, setCounts] = useState({});
  const [wanted, setWanted] = useState(emptyCards());
  const cost = FISH_ITEMS.reduce((s, it) => s + (counts[it.kind] || 0) * prices[it.kind], 0)
    + total(wanted) * prices.resource;
  const tokens = chosen.map((i) => fish[i]);
  const paid = tokens.reduce((a, b) => a + b, 0);
  const spare = tokens.length > 0 && paid - Math.min(...tokens) >= cost;
  const ok = cost > 0 && paid >= cost && !spare;
  const buy = () => {
    const items = FISH_ITEMS.flatMap((it) => Array(counts[it.kind] || 0).fill({ kind: it.kind }))
      .concat(RESOURCES.flatMap((r) => Array(wanted[r]).fill({ kind: 'resource', resource: r })));
    send({ type: 'fish', tokens, items }).then((done) => done && onClose());
  };
  const set = (kind, n) => setCounts({ ...counts, [kind]: n });
  return html`<${Popup} title="Spend fish" onClose=${onClose} wide>
    <div class="trade-label">Pay with</div>
    <${FishChooser} fish=${fish} chosen=${chosen} onChange=${setChosen} />
    <div class="fish-items">
      ${FISH_ITEMS.map((it) => {
        const max = it.max(game, me);
        const n = counts[it.kind] || 0;
        return html`<div key=${it.kind} class=${'fish-item' + (max === 0 ? ' unavailable' : '')}>
          <span class="price">${prices[it.kind]}</span>
          <span class="fish-item-label">${it.label}</span>
          <button class="small" disabled=${n === 0} onClick=${() => set(it.kind, n - 1)}>−</button>
          <b>${n}</b>
          <button class="small" disabled=${n >= max} onClick=${() => set(it.kind, n + 1)}>+</button>
        </div>`;
      })}
    </div>
    <div class="trade-label"><span class="price">${prices.resource}</span> each: a resource of your choice</div>
    <${CardPicker} value=${wanted} onChange=${setWanted} />
    <div class="popup-actions">
      <span class=${spare ? 'warn' : 'muted'}>
        ${spare ? 'You don\'t need all of those tokens.' : `Cost ${cost} · paying ${paid}`}</span>
      <button class="primary" disabled=${!ok} onClick=${buy}>Buy</button>
    </div>
  <//>`;
}

// ------------------------------------------------------ bank and cards

export function DepositPopup({ game, me, send, onClose }) {
  return html`<${Popup} title="Put cards in your bank" onClose=${onClose}>
    <p class="muted small">Banked cards are safe but can't be used. Taking them all out costs 1 fish.</p>
    <${CardSelect} available=${game.players[me].hand} label="Bank them"
      onSubmit=${(cards) => send({ type: 'deposit', cards }).then((ok) => ok && onClose())} />
  <//>`;
}

export function YearOfPlentyPopup({ send, onClose }) {
  return html`<${Popup} title="Year of plenty: take 2" onClose=${onClose}>
    <${CardSelect} count=${2} label="Take"
      onSubmit=${(cards) => send({ type: 'play_dev', card: 'year_of_plenty', cards }).then((ok) => ok && onClose())} />
  <//>`;
}

export function MonopolyPopup({ send, onClose }) {
  return html`<${Popup} title="Monopoly: name a resource" onClose=${onClose}>
    <div class="select-row">
      ${RESOURCES.map((r) => html`<button key=${r} class="card-btn"
        onClick=${() => send({ type: 'play_dev', card: 'monopoly', resource: r }).then((ok) => ok && onClose())}>
        <${ResCard} res=${r} badge=${false} /></button>`)}
    </div>
  <//>`;
}
