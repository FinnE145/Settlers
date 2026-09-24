// Small shared UI helpers.
import { h } from 'preact';
import htm from 'htm';

const html = htm.bind(h);

export const RESOURCES = ['wood', 'brick', 'sheep', 'wheat', 'ore'];

export const total = (cards) => Object.values(cards).reduce((a, b) => a + b, 0);
export const emptyCards = () => Object.fromEntries(RESOURCES.map((r) => [r, 0]));

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
