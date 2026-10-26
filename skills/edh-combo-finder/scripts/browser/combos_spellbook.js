// EDH skills browser snippet: Commander Spellbook find-my-combos + estimate-bracket -> find_combos.py --response.
// Run on a https://commanderspellbook.com page: the backend only answers requests from its own origin.
// Deck input, first match wins:
//   1. DECK_URL below (Moxfield, Archidekt, Deckstats, TappedOut) - Spellbook reads the list itself, or
//   2. window.DECK = {...} run first (print it with: python scripts/edh_common.py names-js deck.json)
// Output is slimmed (no image URLs) and chunked: this returns "chunks=N"; evaluate window.__edh[0] .. [N-1],
// save each verbatim (quotes included) as part-0.txt ...; then: python scripts/edh_common.py join spellbook.json part-*.txt
// Please keep Spellbook's credit and link in anything you show users.
await (async () => {
  const DECK_URL = '';   // e.g. 'https://moxfield.com/decks/abc123' ; leave '' to use window.DECK
  const CHUNK = 24000;
  const API = 'https://backend.commanderspellbook.com';
  const out = (obj) => { const s = JSON.stringify(obj); window.__edh = []; for (let i = 0; i < s.length; i += CHUNK) window.__edh.push(s.slice(i, i + CHUNK)); return `chunks=${window.__edh.length} bytes=${s.length} -> now evaluate window.__edh[0] .. window.__edh[${window.__edh.length - 1}]`; };
  const post = async (path, body) => { const r = await fetch(API + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error(`${path} -> HTTP ${r.status}`); return r.json(); };

  let body;
  if (DECK_URL) {
    const r = await fetch(`${API}/card-list-from-url?url=${encodeURIComponent(DECK_URL)}`);
    if (!r.ok) throw new Error(`card-list-from-url -> HTTP ${r.status}`);
    body = await r.json();
  } else if (window.DECK) body = window.DECK;
  else throw new Error('Set DECK_URL or run window.DECK = {...} first.');

  // Complete combos keep prerequisites and steps; near-combos keep only what ranking needs (keeps the payload small).
  const slimV = (v, full = true) => ({ id: v.id, uses: v.uses.map(u => ({ card: { name: u.card.name } })),
    produces: v.produces.map(p => ({ feature: { name: p.feature.name } })),
    requires: (v.requires || []).map(q => ({ template: { name: q.template.name } })),
    bracketTag: v.bracketTag, manaNeeded: v.manaNeeded, manaValueNeeded: v.manaValueNeeded, identity: v.identity,
    legalities: { commander: (v.legalities || {}).commander }, popularity: v.popularity, salt: v.salt ?? undefined,
    ...(full ? { easyPrerequisites: v.easyPrerequisites, notablePrerequisites: v.notablePrerequisites,
                 description: (v.description || '').slice(0, 400) } : {}) });

  let page = await post('/find-my-combos/', body);
  const res = page.results;
  while (page.next) { page = await post(page.next.replace(API, ''), body);   // paginated responses, if any
    for (const [k, v] of Object.entries(page.results)) if (Array.isArray(v)) res[k] = (res[k] || []).concat(v); }
  let estimate = null;
  try { const e = await post('/estimate-bracket/', body);
    estimate = { bracketTag: e.bracketTag, combos: (e.combos || []).map(c => ({ id: c.combo && c.combo.id, bracketTag: c.bracketTag ?? (c.combo && c.combo.bracketTag) })) };
  } catch (err) { estimate = { error: String(err) }; }

  const results = { identity: res.identity, included: (res.included || []).map(v => slimV(v, true)), almostIncluded: (res.almostIncluded || []).map(v => slimV(v, false)) };
  const other = {}; for (const [k, v] of Object.entries(res)) if (Array.isArray(v) && !(k in results)) other[k] = v.length;
  return out({ results, other_bucket_counts: other, estimate_bracket: estimate, deck_size: (body.main || []).length + (body.commanders || []).length,
               source: 'commanderspellbook.com (browser)', fetched_at: new Date().toISOString() });
})();
