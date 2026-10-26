// EDH skills browser snippet: card data for the user's COLLECTION -> candidates.py --collection-cards.
// Works on ANY origin (Scryfall's API allows cross-origin requests).
// First run the lines printed by:  python scripts/collection.py to-js <collection file> --deck deck.json
//   (they set window.COLLECTION = [names...] and window.IDENTITY = "WUBR"; cards already in the deck and basics
//   are left out already). Then run this.
// Keeps only cards that can go in the deck: inside the commander's colour identity, legal in Commander, paper,
// not basic lands. If more than MAX remain, keeps the MAX most-played (lowest EDHREC rank) and reports the rest.
// WITH_TAGS attaches role-relevant Scryfall oracle tags (downloads the ~6 MB Oracle Tags file) for better tagging.
// Output: card table {"schema":"edh-cards-table/1","fields":[...],"rows":[...],"not_found":[...]} in ~24 KB chunks.
// This returns "chunks=N"; evaluate window.__edh[0] .. [N-1], save each verbatim (quotes included) as
// part-0.txt ...; then:  python scripts/edh_common.py join owned_cards.json part-*.txt
await (async () => {
  const MAX = 250;          // cards returned (each ~0.5 KB)
  const WITH_TAGS = true;
  const CHUNK = 24000;
  const T = (x) => (x == null ? null : x.length > 400 ? x.slice(0, 400) + '…' : x);
  const out = (obj) => { const s = JSON.stringify(obj); window.__edh = []; for (let i = 0; i < s.length; i += CHUNK) window.__edh.push(s.slice(i, i + CHUNK)); return `chunks=${window.__edh.length} bytes=${s.length} kept=${obj.rows.length} -> now evaluate window.__edh[0] .. window.__edh[${window.__edh.length - 1}]`; };
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  if (!Array.isArray(window.COLLECTION) || !window.COLLECTION.length) throw new Error('Run the window.COLLECTION lines printed by collection.py to-js first.');
  const ident = new Set((window.IDENTITY || 'WUBRG').split(''));
  const names = [...new Set(window.COLLECTION)];

  const cards = [], notFound = [];
  for (let i = 0; i < names.length; i += 75) {             // Scryfall: 75 identifiers per call, 2 calls/s
    const r = await fetch('https://api.scryfall.com/cards/collection', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifiers: names.slice(i, i + 75).map(n => ({ name: n.split(' // ')[0] })) }) });
    if (r.status === 429) { await sleep(31000); i -= 75; continue; }
    const d = await r.json(); cards.push(...d.data); notFound.push(...(d.not_found || []).map(x => x.name));
    await sleep(600);
  }
  const fits = (c) => (c.color_identity || []).every(x => ident.has(x)) && (c.legalities || {}).commander === 'legal'
    && !c.digital && !/^Basic /.test(c.type_line || '');
  let keep = cards.filter(fits);
  const offIdentityOrIllegal = cards.length - keep.length;
  keep.sort((a, b) => (a.edhrec_rank ?? 1e9) - (b.edhrec_rank ?? 1e9));
  const overCap = keep.slice(MAX).map(c => c.name);
  keep = keep.slice(0, MAX);

  const FIELDS = ['oracle_id', 'name', 'layout', 'mana_cost', 'cmc', 'type_line', 'oracle_text', 'color_identity', 'produced_mana',
    'legal_commander', 'game_changer', 'usd', 'rarity', 'edhrec_rank', 'card_faces', 'otags'];
  const rows = new Map(keep.map(c => [c.oracle_id || (c.card_faces && c.card_faces[0].oracle_id), [c.oracle_id || (c.card_faces && c.card_faces[0].oracle_id),
    c.name, c.layout, c.mana_cost ?? null, c.cmc, c.type_line, T(c.oracle_text), (c.color_identity || []).join(''),
    (c.produced_mana || []).join('') || null, (c.legalities || {}).commander, !!c.game_changer, (c.prices || {}).usd ?? null,
    c.rarity, c.edhrec_rank ?? null, c.card_faces ? c.card_faces.map(f => [f.name, f.mana_cost || '', f.type_line || '', T(f.oracle_text || '')]) : null, null]]));

  if (WITH_TAGS && rows.size) {
    const RELEVANT = /^(ramp|mana-rock|utility-mana-rock|mana-dork|land-ramp|multi-land-ramp|cost-reducer|treasure-generator|ritual|draw-engine|repeatable-(pure-draw|draw|card-advantage|impulsive-draw|creature-tokens|artifact-tokens|sacrifice-outlet)|card-advantage|burst-draw|pure-draw|cantrip|impulsive-draw|wheel|removal-.+|spot-removal|multi-removal|swap-removal|counterspell.*|bounce|edict|sweeper.*|board-wipe|mass-removal|mass-bounce|gives-(hexproof|protection|indestructible|shroud|player-hexproof)|phasing|tax-attack|pillowfort|tutor-.+|reanimate-.+|mass-reanimation|recursion-.+|win-condition|alternate-win-condition|sacrifice-outlet.*|free-sacrifice-outlet|land-destruction|extra-turn|stax|polymorph|consult-onto-battlefield|sneak-.+)$/;
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
               dropped_off_identity_or_illegal: offIdentityOrIllegal, dropped_over_cap: overCap, identity: [...ident].join(''),
               source: 'collection (scryfall, browser)', fetched_at: new Date().toISOString() });
})();
