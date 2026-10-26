// EDH skills browser snippet: resolve the deck's cards on Scryfall -> card table for enrich.py --cards-json.
// Works on ANY origin (Scryfall's API allows cross-origin requests). Deck input, first match wins:
//   1. window.__edhDeck left by moxfield_deck.js in the same tab (resolves by Scryfall ID), or
//   2. window.DECK = {...} pasted and run first (print it with: python scripts/edh_common.py names-js parsed.json)
// WITH_TAGS downloads Scryfall's Oracle Tags bulk file (~6 MB gzip) and attaches each card's role-relevant
// tags as `otags` (direct taggings only; tag_roles.py maps the specific slugs).
// Output: compact table {"schema":"edh-cards-table/1","fields":[...],"rows":[...]} in ~24 KB chunks.
// This returns "chunks=N"; evaluate window.__edh[0] .. window.__edh[N-1], save each verbatim (quotes included)
// as part-0.txt, part-1.txt, ... then: python scripts/edh_common.py join cards.json part-*.txt
await (async () => {
  const WITH_TAGS = true;
  const CHUNK = 24000;
  const out = (obj) => { const s = JSON.stringify(obj); window.__edh = []; for (let i = 0; i < s.length; i += CHUNK) window.__edh.push(s.slice(i, i + CHUNK)); return `chunks=${window.__edh.length} bytes=${s.length} -> now evaluate window.__edh[0] .. window.__edh[${window.__edh.length - 1}]`; };
  const FIELDS = ['oracle_id', 'name', 'layout', 'mana_cost', 'cmc', 'type_line', 'oracle_text', 'color_identity', 'produced_mana',
    'legal_commander', 'game_changer', 'usd', 'rarity', 'edhrec_rank', 'card_faces', 'otags'];
  const row = (c) => [c.oracle_id || (c.card_faces && c.card_faces[0].oracle_id), c.name, c.layout, c.mana_cost ?? null, c.cmc,
    c.type_line, c.oracle_text ?? null, (c.color_identity || []).join(''), (c.produced_mana || []).join('') || null,
    (c.legalities || {}).commander, !!c.game_changer, (c.prices || {}).usd ?? null, c.rarity, c.edhrec_rank ?? null,
    c.card_faces ? c.card_faces.map(f => [f.name, f.mana_cost || '', f.type_line || '', f.oracle_text || '']) : null, null];
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));

  let idents;
  if (window.__edhDeck && window.__edhDeck.length) {
    idents = [...new Map(window.__edhDeck.filter(e => ['main', 'commander', 'companion', 'sideboard'].includes(e.board))
      .map(e => e.scryfall_id ? [e.scryfall_id, { id: e.scryfall_id }] : [e.name, { name: e.name }])).values()];
  } else if (window.DECK) {
    idents = [...new Set([...window.DECK.commanders, ...window.DECK.main].map(x => x.card))].map(name => ({ name: name.split(' // ')[0] }));
  } else throw new Error('No deck: run moxfield_deck.js in this tab first, or run window.DECK = {...} first.');

  const cards = [], notFound = [];
  for (let i = 0; i < idents.length; i += 75) {            // Scryfall: 75 identifiers per call, 2 calls/s
    const r = await fetch('https://api.scryfall.com/cards/collection', { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ identifiers: idents.slice(i, i + 75) }) });
    if (r.status === 429) { await sleep(31000); i -= 75; continue; }
    const d = await r.json(); cards.push(...d.data); notFound.push(...(d.not_found || []));
    await sleep(600);
  }
  const rows = new Map(cards.map(c => { const r = row(c); return [r[0], r]; }));

  if (WITH_TAGS) {
    const RELEVANT = /^(ramp|ramp-with-set-s-mechanic|mana-rock|utility-mana-rock|mana-dork|land-ramp|multi-land-ramp|cost-reducer|treasure-generator|ritual|draw-engine|repeatable-(pure-draw|draw|card-advantage|impulsive-draw|creature-tokens|artifact-tokens|sacrifice-outlet)|card-advantage|burst-draw|pure-draw|cantrip|impulsive-draw|long-term-impulsive-draw|wheel|removal-.+|spot-removal|multi-removal|swap-removal|counterspell.*|bounce|edict|sweeper.*|board-wipe|mass-removal|mass-bounce|gives-(hexproof|protection|indestructible|shroud|player-hexproof)|protection|phasing|tax-attack|pillowfort|tutor-.+|reanimate-.+|mass-reanimation|recursion-.+|win-condition|alternate-win-condition|sacrifice-outlet.*|free-sacrifice-outlet|land-destruction|extra-turn|stax|polymorph|consult-onto-battlefield|sneak-.+)$/;
    const meta = await (await fetch('https://api.scryfall.com/bulk-data')).json();
    const tb = meta.data.find(b => b.type === 'oracle_tags');
    const txt = await new Response((await fetch(tb.jsonl_download_uri || tb.download_uri)).body.pipeThrough(new DecompressionStream('gzip'))).text();
    for (const line of txt.split('\n')) {
      if (!line) continue;
      const t = JSON.parse(line);
      if (!RELEVANT.test(t.slug)) continue;
      for (const g of t.taggings || []) { const r = rows.get(g.oracle_id); if (r) r[15] = [...new Set([...(r[15] || []), t.slug])].sort(); }
    }
  }
  return out({ schema: 'edh-cards-table/1', fields: FIELDS, rows: [...rows.values()], not_found: notFound,
               tags_included: WITH_TAGS, fetched_at: new Date().toISOString() });
})();
