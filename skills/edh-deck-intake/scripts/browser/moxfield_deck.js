// EDH skills browser snippet: Moxfield deck -> parsed.json (parse_decklist.py output format).
// Run on the deck's own page: https://moxfield.com/decks/<publicId>  (api2.moxfield.com only answers that origin).
// Result is chunked: this returns "chunks=N"; then evaluate window.__edh[0], window.__edh[1], ... and
// save each result verbatim (quotes included) as part-0.txt, part-1.txt, ... then:
//   python scripts/edh_common.py join parsed.json part-*.txt
// Also leaves window.__edhDeck (with Scryfall IDs) so cards_scryfall.js can run next in the same tab.
// Entries are slim ({qty, name, board}); set INCLUDE_MAYBEBOARD = true to keep maybeboard cards.
await (async () => {
  const INCLUDE_MAYBEBOARD = false;
  const CHUNK = 24000;
  const out = (obj) => { const s = JSON.stringify(obj); window.__edh = []; for (let i = 0; i < s.length; i += CHUNK) window.__edh.push(s.slice(i, i + CHUNK)); return `chunks=${window.__edh.length} bytes=${s.length} -> now evaluate window.__edh[0] .. window.__edh[${window.__edh.length - 1}]`; };

  const ID = location.pathname.split('/').filter(Boolean).pop();
  const resp = await fetch(`https://api2.moxfield.com/v3/decks/all/${ID}`);
  if (!resp.ok) throw new Error(`Moxfield returned ${resp.status} (private deck, or not on a moxfield.com page?)`);
  const j = await resp.json();
  const BOARDS = { commanders: 'commander', companions: 'companion', mainboard: 'main', sideboard: 'sideboard' };
  if (INCLUDE_MAYBEBOARD) BOARDS.maybeboard = 'maybeboard';
  const entries = [];
  for (const [b, board] of Object.entries(BOARDS)) {
    for (const v of Object.values((j.boards[b] || {}).cards || {})) {
      entries.push({ qty: v.quantity, name: v.card.name, board, scryfall_id: v.card.scryfall_id });
    }
  }
  window.__edhDeck = entries;
  const slimEntries = entries.map(({ qty, name, board }) => ({ qty, name, board }));
  const total = entries.filter(e => e.board === 'main' || e.board === 'commander').reduce((a, e) => a + e.qty, 0);
  return out({ format_guess: 'url:moxfield-browser', url: location.href, name: j.name, entries: slimEntries,
        warnings: total === 100 ? [] : [`Main deck + commander(s) = ${total} cards.`] });
})();
