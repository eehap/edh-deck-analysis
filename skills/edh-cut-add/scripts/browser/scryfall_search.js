// EDH skills browser snippet: run candidates.py's per-gap Scryfall queries -> candidates.py --candidates-json.
// Works on ANY origin (Scryfall allows cross-origin requests).
// First run the `window.QUERIES = {...};` line that candidates.py printed (role -> Scryfall query), then this.
// Output: card table {"schema":"edh-cards-table/1", "fields":[..., "role_hint"], "rows":[...]} in ~24 KB chunks.
// This returns "chunks=N"; evaluate window.__edh[0] .. [N-1], save verbatim as part-0.txt ...; then
//   python scripts/edh_common.py join supplied.json part-*.txt
await (async () => {
  const PER_QUERY = 15;     // cards kept per query (Scryfall orders by EDHREC rank); each adds ~0.5 KB
  const CHUNK = 24000;
  const T = (x) => (x == null ? null : x.length > 400 ? x.slice(0, 400) + '…' : x);
  const out = (obj) => { const s = JSON.stringify(obj); window.__edh = []; for (let i = 0; i < s.length; i += CHUNK) window.__edh.push(s.slice(i, i + CHUNK)); return `chunks=${window.__edh.length} bytes=${s.length} -> now evaluate window.__edh[0] .. window.__edh[${window.__edh.length - 1}]`; };
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  if (!window.QUERIES) throw new Error('Run the window.QUERIES = {...}; line printed by candidates.py first.');
  const FIELDS = ['oracle_id', 'name', 'layout', 'mana_cost', 'cmc', 'type_line', 'oracle_text', 'color_identity', 'produced_mana',
    'legal_commander', 'game_changer', 'usd', 'rarity', 'edhrec_rank', 'card_faces', 'role_hint'];
  const rows = [], seen = new Set(), errors = {};
  for (const [role, q] of Object.entries(window.QUERIES)) {
    const r = await fetch('https://api.scryfall.com/cards/search?order=edhrec&q=' + encodeURIComponent(q));
    await sleep(600);                                    // Scryfall search: 2 requests per second
    if (r.status === 404) { errors[role] = 'no cards matched'; continue; }
    if (!r.ok) { errors[role] = `HTTP ${r.status}`; continue; }
    const d = await r.json();
    for (const c of d.data.slice(0, PER_QUERY)) {
      if (seen.has(c.name)) continue; seen.add(c.name);
      rows.push([c.oracle_id || (c.card_faces && c.card_faces[0].oracle_id), c.name, c.layout, c.mana_cost ?? null, c.cmc, c.type_line,
        T(c.oracle_text), (c.color_identity || []).join(''), (c.produced_mana || []).join('') || null, (c.legalities || {}).commander,
        !!c.game_changer, (c.prices || {}).usd ?? null, c.rarity, c.edhrec_rank ?? null,
        c.card_faces ? c.card_faces.map(f => [f.name, f.mana_cost || '', f.type_line || '', T(f.oracle_text || '')]) : null, role]);
    }
  }
  return out({ schema: 'edh-cards-table/1', fields: FIELDS, rows, errors, source: 'scryfall search (browser)', fetched_at: new Date().toISOString() });
})();
