// Small shared UI pieces.
import { h } from 'preact';
import htm from 'htm';

const html = htm.bind(h);

export const RESOURCES = ['wood', 'brick', 'sheep', 'wheat', 'ore'];

export function Chip({ res, n }) {
  return html`<span class=${'chip r-' + res} title=${res}>
    <span class="chip-name">${res}</span>${n != null && html`<b>${n}</b>`}
  </span>`;
}

export function Cards({ cards, empty = 'none' }) {
  const shown = RESOURCES.filter((r) => cards[r]);
  if (!shown.length) return html`<span class="muted">${empty}</span>`;
  return html`<span class="cards">${shown.map((r) => html`<${Chip} key=${r} res=${r} n=${cards[r]} />`)}</span>`;
}

export function Cost({ cost }) {
  return html`<span class="cost">${Object.entries(cost).map(([r, n]) =>
    html`<span key=${r} class=${'dot r-' + r} title=${`${n} ${r}`}>${n > 1 ? n : ''}</span>`)}</span>`;
}

export const total = (cards) => Object.values(cards).reduce((a, b) => a + b, 0);
export const emptyCards = () => Object.fromEntries(RESOURCES.map((r) => [r, 0]));

/** +/- selector per resource. ``available`` caps each count (null = unlimited). */
export function CardPicker({ value, onChange, available = null, max = Infinity }) {
  const sum = total(value);
  const set = (r, d) => onChange({ ...value, [r]: value[r] + d });
  return html`<div class="picker">
    ${RESOURCES.map((r) => {
      const canAdd = sum < max && (available == null || value[r] < available[r]);
      return html`<div key=${r} class="picker-row">
        <${Chip} res=${r} n=${available ? available[r] : null} />
        <button class="small" disabled=${value[r] <= 0} onClick=${() => set(r, -1)}>−</button>
        <span class="picker-n">${value[r]}</span>
        <button class="small" disabled=${!canAdd} onClick=${() => set(r, 1)}>+</button>
      </div>`;
    })}
  </div>`;
}

/** A read-only link with a copy button (clipboard access needs a secure context,
 * which a plain-http Tailscale address isn't, so fall back to selecting the text). */
export function LinkBox({ label, url }) {
  let input;
  const copy = async () => {
    input.select();
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      document.execCommand('copy');
    }
  };
  return html`<div class="linkbox">
    <div class="muted">${label}</div>
    <div class="linkbox-row">
      <input readonly value=${url} ref=${(el) => { input = el; }} onFocus=${(e) => e.target.select()} />
      <button onClick=${copy}>Copy</button>
    </div>
  </div>`;
}
