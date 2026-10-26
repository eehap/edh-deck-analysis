// EDH skills browser snippet: EDHREC commander page + Scryfall card data -> candidates.py --edhrec-json.
// json.edhrec.com and api.scryfall.com both answer cross-origin requests; running it on an edhrec.com page is
// the safest choice. EDHREC has no official API: keep it to one call per deck, and attribute EDHREC.
// Set SLUG (edhrec.com/commanders/<slug>; partners are both slugs joined alphabetically).
// Optional: run window.DECK = {...} first (python scripts/edh_common.py names-js deck.json) so cards already in
// the deck are reported as deck stats instead of candidates.
// Output (chunked): {"source":"edhrec","slug","num_decks","deck_card_stats":{name:{synergy,inclusion_rate,list}},
//   "schema":"edh-cards-table/1","fields":[...],"rows":[...] (the TOP candidates with card data + EDHREC stats)}
// This returns "chunks=N"; evaluate window.__edh[0] .. [N-1], save verbatim as part-0.txt ...; then
//   python scripts/edh_common.py join edhrec.json part-*.txt
await (async () => {
  const SLUG = 'jace-multiverse-architect';
  const TOP = 40;          // candidates to return with card data (each adds ~0.5 KB)
  const T = (x) => (x == null ? null : x.length > 400 ? x.slice(0, 400) + '…' : x);   // trim long oracle text
  const CHUNK = 24000;
  const out = (obj) => { const s = JSON.stringify(obj); window.__edh = []; for (let i = 0; i < s.length; i += CHUNK) window.__edh.push(s.slice(i, i + CHUNK)); return `chunks=${window.__edh.length} bytes=${s.length} -> now evaluate window.__edh[0] .. window.__edh[${window.__edh.length - 1}]`; };
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const r = await fetch(`https://json.edhrec.com/pages/commanders/${SLUG}.json`);
  if (!r.ok) throw new Error(`EDHREC returned ${r.status} for slug ${SLUG}`);
  const j = await r.json();
  const lists = ((j.container || {}).json_dict || {}).cardlists || [];
  const stats = {};
  for (const l of lists) for (const c of l.cardviews || []) {
    if (stats[c.name]) continue;
    const n = c.num_decks ?? c.inclusion, p = c.potential_decks;
    stats[c.name] = { synergy: c.synergy ?? null, inclusion_rate: n && p ? Math.round(n / p * 1000) / 1000 : null, list: l.header };
  }
  const inDeck = new Set(window.DECK ? [...window.DECK.commanders, ...window.DECK.main].map(x => x.card) : []);
  const score = (s) => (s.synergy || 0) * 2 + (s.inclusion_rate || 0);
  const top = Object.entries(stats).filter(([n]) => !inDeck.has(n)).sort((a, b) => score(b[1]) - score(a[1])).slice(0, TOP).map(([n]) => n);
  const FIELDS = ['oracle_id', 'name', 'layout', 'mana_cost', 'cmc', 'type_line', 'oracle_text', 'color_identity', 'produced_mana',
    'legal_commander', 'game_changer', 'usd', 'rarity', 'edhrec_rank', 'card_faces', 'synergy', 'inclusion_rate', 'edhrec_list'];
  const rows = [];
  for (let i = 0; i < top.length; i += 75) {
    const resp = await fetch('https://api.scryfall.com/cards/collection', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifiers: top.slice(i, i + 75).map(name => ({ name: name.split(' // ')[0] })) }) });
    const d = await resp.json();
    for (const c of d.data) {
      const s = stats[c.name] || stats[c.name.split(' // ')[0]] || {};
      rows.push([c.oracle_id || (c.card_faces && c.card_faces[0].oracle_id), c.name, c.layout, c.mana_cost ?? null, c.cmc, c.type_line,
        T(c.oracle_text), (c.color_identity || []).join(''), (c.produced_mana || []).join('') || null, (c.legalities || {}).commander,
        !!c.game_changer, (c.prices || {}).usd ?? null, c.rarity, c.edhrec_rank ?? null,
        c.card_faces ? c.card_faces.map(f => [f.name, f.mana_cost || '', f.type_line || '', T(f.oracle_text || '')]) : null,
        s.synergy ?? null, s.inclusion_rate ?? null, s.list ?? null]);
    }
    await sleep(600);
  }
  const deckStats = {}; for (const n of inDeck) if (stats[n]) deckStats[n] = stats[n];
  return out({ source: 'edhrec', slug: SLUG, num_decks: j.num_decks_avg ?? j.num_decks ?? null, cards_on_page: Object.keys(stats).length,
               deck_card_stats: deckStats, schema: 'edh-cards-table/1', fields: FIELDS, rows, fetched_at: new Date().toISOString() });
})();
