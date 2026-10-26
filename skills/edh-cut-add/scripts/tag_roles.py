#!/usr/bin/env python3
"""Tag every card in deck.json with functional roles from oracle-text rules + Scryfall oracle tags.

Roles (weights 1.0 / 0.5 / 0.25, max 3 per card; land is always kept):
  land, ramp, card_advantage, targeted_interaction, mass_interaction, protection,
  tutor, recursion, wincon, engine, tokens
Flags (no weight, don't count toward the cap):
  ritual, sac_outlet, draw_engine, draw_burst, cantrip, graveyard_hate, stax, mld, land_destruction,
  extra_turn, game_changer, symmetrical_wipe, tapped_land, conditional_untapped, pillow_fort,
  polymorph, reveal_until, reveal_until_creature, reveal_until_creature_or_pw, cheat_into_play,
  reanimation, artifact_tokens

How the two signals combine:
  - Oracle text is read with ownership in mind: removal and wipes only count when they can hit an
    opponent's permanent ("exile target creature you control" is not removal; "exile all creatures
    you control" is not a wipe). Ramp only counts mana YOU get from this card's own ability or spell;
    granted abilities in quotes ("target land gains '{T}: Add {C}{C}'") and opponents' Treasures don't.
  - Oracle tags (community-maintained) add roles the rules miss, but text rules can VETO them:
    polymorph cards keep no wipe/removal from tags, and tag-only ramp is dropped unless the text
    shows own mana production (tags such as land-ramp also cover stealing an opponent's land).
Confidence: high = rule and tag agree; medium = one source; low = weak/conditional pattern.
Cards land in `needs_review` when signals disagree, only weak signals fired, or a nonland card got
no role. The model resolves those in overrides.json (see SKILL.md); structure_report.py merges it.

Usage: python tag_roles.py deck.json -o roles.json
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from edh_common import card_text, card_type_line, dump_json, load_json  # noqa: E402

ROLES = ["land", "ramp", "card_advantage", "targeted_interaction", "mass_interaction",
         "protection", "tutor", "recursion", "wincon", "engine", "tokens"]

# ---------------- oracle tags -> roles / flags ----------------
# Specific slugs only: umbrella tags with no direct taggings ("removal", "draw", "tutor", "recursion",
# "protection") reach us only as ancestors from the bulk loader and would double count, so they're ignored.
OTAG_EXACT = {
    "ramp": ("ramp", 1.0), "ramp-with-set-s-mechanic": ("ramp", 1.0), "mana-rock": ("ramp", 1.0),
    "utility-mana-rock": ("ramp", 1.0), "mana-dork": ("ramp", 1.0), "mana-dork-egg": ("ramp", 1.0),
    "land-ramp": ("ramp", 1.0), "multi-land-ramp": ("ramp", 1.0), "tutor-land-to-battlefield": ("ramp", 1.0),
    "cost-reducer": ("ramp", 0.5), "treasure-generator": ("ramp", 0.5), "ritual": ("ritual", 0),
    "draw-engine": ("card_advantage", 1.0), "repeatable-pure-draw": ("card_advantage", 1.0),
    "repeatable-draw": ("card_advantage", 1.0), "repeatable-card-advantage": ("card_advantage", 1.0),
    "card-advantage": ("card_advantage", 1.0), "burst-draw": ("card_advantage", 1.0),
    "pure-draw": ("card_advantage", 1.0), "cantrip": ("card_advantage", 0.25),
    "impulsive-draw": ("card_advantage", 0.5), "long-term-impulsive-draw": ("card_advantage", 0.5),
    "repeatable-impulsive-draw": ("card_advantage", 0.5), "wheel": ("card_advantage", 0.5),
    "spot-removal": ("targeted_interaction", 1.0), "multi-removal": ("targeted_interaction", 1.0),
    "swap-removal": ("targeted_interaction", 1.0), "counterspell": ("targeted_interaction", 1.0),
    "bounce": ("targeted_interaction", 0.5), "edict": ("targeted_interaction", 0.5),
    "removal-bounce": ("targeted_interaction", 0.5), "removal-sacrifice": ("targeted_interaction", 0.5),
    "removal-land": ("land_destruction", 0), "land-destruction": ("land_destruction", 0),
    "sweeper": ("mass_interaction", 1.0), "sweeper-one-sided": ("mass_interaction", 1.0),
    "board-wipe": ("mass_interaction", 1.0), "mass-removal": ("mass_interaction", 1.0),
    "mass-bounce": ("mass_interaction", 1.0), "sweeper-graveyard": ("graveyard_hate", 0),
    "gives-hexproof": ("protection", 1.0), "gives-protection": ("protection", 1.0),
    "gives-indestructible": ("protection", 1.0), "gives-shroud": ("protection", 1.0),
    "gives-player-hexproof": ("protection", 1.0), "phasing": ("protection", 0.5),
    "tax-attack": ("protection", 1.0), "pillowfort": ("protection", 1.0),
    "mass-reanimation": ("recursion", 1.0), "reanimate-self": ("recursion", 0.25),
    "win-condition": ("wincon", 1.0), "alternate-win-condition": ("wincon", 1.0),
    "free-sacrifice-outlet": ("sac_outlet", 0), "extra-turn": ("extra_turn", 0), "stax": ("stax", 0),
    "polymorph": ("engine", 1.0), "consult-onto-battlefield": ("reveal_until", 0),
    "repeatable-creature-tokens": ("tokens", 1.0), "repeatable-artifact-tokens": ("artifact_tokens", 0),
}
OTAG_FLAG_EXTRA = {"tax-attack": "pillow_fort", "pillowfort": "pillow_fort", "polymorph": "polymorph",
                   "sneak-creature": "cheat_into_play", "sneak-planeswalker": "cheat_into_play"}


def otag_signals(otags: list[str]) -> tuple[dict[str, float], set[str]]:
    roles: dict[str, float] = {}
    flags: set[str] = set()

    def put(role, w):
        if role in ROLES:
            roles[role] = max(roles.get(role, 0), w)
        else:
            flags.add(role)

    for t in otags or []:
        if t in OTAG_FLAG_EXTRA:
            flags.add(OTAG_FLAG_EXTRA[t])
        if t in OTAG_EXACT:
            put(*OTAG_EXACT[t])
        elif t.startswith("tutor-land"):
            continue                                   # land search: ramp only via tutor-land-to-battlefield
        elif t.startswith("tutor-") and t not in ("tutor-self",):
            put("tutor", 1.0)
        elif t.startswith("removal-"):
            put("targeted_interaction", 1.0)
        elif t.startswith("counterspell"):
            put("targeted_interaction", 1.0)
        elif t.startswith("sweeper"):
            put("mass_interaction", 1.0)
        elif (t.startswith("reanimate-") or t.startswith("recursion-")) and not t.endswith("-self"):
            put("recursion", 1.0)
            if t.startswith("reanimate-"):
                flags.add("reanimation")
        elif t.startswith("sacrifice-outlet") or t == "repeatable-sacrifice-outlet":
            flags.add("sac_outlet")
    return roles, flags


# ---------------- oracle-text rules ----------------
def _strip_reminder(t: str) -> str:
    return re.sub(r"\([^)]*\)", "", t)


def _strip_quoted(t: str) -> str:
    """Remove abilities granted in quotes - they belong to another object, not this card."""
    return re.sub(r'"[^"]*"', '""', t)


LAND_TYPES = r"(?:basic land|land|Plains|Island|Swamp|Mountain|Forest|Wastes|Desert|Gate|Cave)"
SEARCH_LAND = re.compile(rf"search your library for (?:up to \w+ )?(?:a |an |two |three )?(?:basic )?{LAND_TYPES}"
                         rf"(?: cards?)?(?:,? (?:or|and/or) (?:a |an )?{LAND_TYPES}(?: cards?)?)*"
                         rf"|search your library for an? (?:basic )?(?:Plains|Island|Swamp|Mountain|Forest)(?:, \w+)*,? or \w+ card", re.I)
SEARCH_ANY = re.compile(r"search your library for (?:up to \w+ )?(?:an? |two |three |X )?([\w\s,\-]*?)cards?", re.I)
REVEAL_UNTIL = re.compile(r"reveals? cards from the top of (?:your|their|his or her) library until (?:you|they|he or she) "
                          r"reveals? (?:a|an|that many|\w+) ([a-z ,]*?)cards?", re.I)
TARGET_ACTION = re.compile(r"\b(destroy|exile|put|return|gain control of)\s+(?:up to (?:one|two|three|\w+) )?(?:another )?"
                           r"(?:other )?(\w+ )?target ([^.;:]*?)(?=[.;:]|,? then | and | to | on the bottom|$)", re.I)
SELF_OWNED = re.compile(r"you control|you own", re.I)


def _targets_opponents(phrase: str) -> bool:
    """True if a 'target ...' phrase can pick an opponent's permanent."""
    return not SELF_OWNED.search(phrase)


def text_signals(card: dict, entry: dict | None = None) -> tuple[dict[str, float], set[str], dict[str, str]]:
    roles: dict[str, float] = {}
    flags: set[str] = set()
    why: dict[str, str] = {}

    def add(role, w, reason):
        if w > roles.get(role, 0):
            roles[role] = w
            why[role] = reason

    tl = card_type_line(card)
    faces = card.get("card_faces") or []
    front_tl = faces[0].get("type_line", tl) if faces and card.get("layout") == "modal_dfc" else tl.split(" // ")[0]
    raw = card_text(card)
    if card.get("layout") == "modal_dfc" and faces and "Land" not in faces[0].get("type_line", ""):
        # spell rules read only the spell face(s); the land face is handled as `land`
        raw = "\n".join(f.get("oracle_text", "") for f in faces if "Land" not in f.get("type_line", ""))
    t = _strip_reminder(raw)
    own = _strip_quoted(t)             # this card's own abilities only
    tlow, ownlow = t.lower(), own.lower()
    cmc = card.get("cmc", 0) or 0
    is_land = "Land" in front_tl
    is_instant_sorcery = "Instant" in front_tl or "Sorcery" in front_tl

    # land
    if is_land:
        add("land", 1.0, "type line")
        if re.search(r"enters (?:the battlefield )?tapped", tlow):
            if re.search(r"unless|if you don't|you may pay \d+ life", tlow):
                flags.add("conditional_untapped")
            else:
                flags.add("tapped_land")
    elif card.get("layout") == "modal_dfc" and any("Land" in f.get("type_line", "") for f in faces[1:]):
        add("land", 1.0 if card.get("rarity") == "mythic" else 0.8, "MDFC with a land back face")

    # ---- polymorph / reveal-until (checked early: it changes how removal and wipes are read) ----
    poly = None
    m = REVEAL_UNTIL.search(t)
    if m and "onto the battlefield" in tlow[m.start(): m.start() + 300]:
        hit = m.group(1).strip().lower()
        flags.add("reveal_until")
        if "planeswalker" in hit:
            flags.add("reveal_until_creature_or_pw")
        elif "creature" in hit:
            flags.add("reveal_until_creature")
        before = tlow[:m.start()]
        exiles_own = re.search(r"(exile|destroy|sacrifice|put)[^.]*?(target (?:\w+ )*?(creature|planeswalker|permanent)[^.]*?you (?:control|own)"
                               r"|all creatures you control|creatures you control)", before)
        exiles_any = re.search(r"(exile|destroy|put)[^.]*?(?:two |another |up to \w+ )?target (?:\w+ )*?creatures?", before)
        if exiles_own:
            poly = "self"
            add("engine", 1.0, "polymorph: swaps your own permanent(s) for random hits from the library")
            flags.add("polymorph")
        elif exiles_any:
            poly = "any"
            add("engine", 1.0, "polymorph: can swap your own permanent (or an opponent's) for a random hit")
            add("targeted_interaction", 0.5, "polymorph on an opponent's creature (they get a random replacement)")
            flags.add("polymorph")
        else:
            add("engine", 0.5, "puts a random creature from the library onto the battlefield")
            flags.add("cheat_into_play")
    if re.search(r"put (?:a|an|up to \w+) (?:\w+ )?(creature|permanent|artifact|planeswalker)[^.]*? card from your hand onto the battlefield", tlow):
        flags.add("cheat_into_play")

    # ---- ramp: mana YOU get from this card ----
    if not is_land:
        if re.search(r"\{T\}(?:, [^:]*)?: Add \{|\{T\}(?:, [^:]*)?: Add (?:one|two|three|X) mana", own) or \
                re.search(r"^\s*[+−-]?\d+: Add \{", own, re.M):
            add("ramp", 1.0, "taps for mana")
        if re.search(r"Sacrifice (?:a|another) (?:creature|artifact)[^:]*: Add", own):
            add("ramp", 0.25, "sacrifice for mana (combo/burst, not steady ramp)")
            flags.add("sac_outlet")
        if is_instant_sorcery and re.search(r"\bAdd \{", own) and not SEARCH_LAND.search(own):
            flags.add("ritual")
        ml = SEARCH_LAND.search(own)
        if ml and "onto the battlefield" in ownlow[ml.start(): ml.start() + 250]:
            add("ramp", 1.0, "puts lands onto the battlefield")
            if cmc >= 3 and "into your hand" in ownlow:
                flags.add("ramp_3mv_split")
        if re.search(r"spells? you cast costs? \{\d\} less|costs? \{\d\} less to cast", own):
            add("ramp", 0.5, "cost reducer")
        if re.search(r"you may play an additional land|play two additional lands", ownlow):
            add("ramp", 0.5, "extra land drops")
        for mt in re.finditer(r"([^.]*?)create (?:a|an|two|three|X|that many) (?:tapped )?Treasure", own):
            if re.search(r"(its controller|that player|target player|each opponent|an opponent)\s*$", mt.group(1).strip(), re.I):
                continue
            repeat = re.search(r"\b(Whenever|At the beginning)\b", own)
            add("ramp", 0.5 if repeat else 0.25, "makes Treasure")
            break

    # ---- card advantage ----
    draw_n = re.search(r"draws? (two|three|four|five|six|seven|X|that many) cards", tlow)
    draw_1 = re.search(r"draws? (?:a|an additional|one) cards?", tlow)
    repeat_draw = re.search(r"(whenever|at the beginning of)[^.]{0,120}draws? (?:a|an additional|one|two|three|cards)", tlow) \
        or re.search(r"(?m)^[^:\n]{1,80}: [^.\n]{0,80}draws? (?:a|two|three) cards?", t) \
        or re.search(r"draw two additional cards|draw an additional card", tlow)
    if repeat_draw:
        add("card_advantage", 1.0, "repeatable draw")
        flags.add("draw_engine")
    elif draw_n:
        add("card_advantage", 1.0, f"draws {draw_n.group(1)}")
        flags.add("draw_burst")
    elif draw_1:
        add("card_advantage", 0.25, "cantrip")
        flags.add("cantrip")
    if re.search(r"(reveal|look at) the top (three|four|five|six|seven|x) cards of your library[^\n]*?(?:put|into) [^.\n]*(?:into your hand|in your hand)", tlow):
        add("card_advantage", 1.0, "digs several cards into hand")
    if re.search(r"exile the top [^.]* cards? of your library\. (?:until|you may (?:play|cast))", tlow):
        add("card_advantage", 0.5, "impulse draw")

    # ---- targeted interaction: only targets an opponent's permanent can be ----
    if poly is None:
        for mt in TARGET_ACTION.finditer(own):
            verb, phrase = mt.group(1).lower(), mt.group(3).lower()
            if not re.search(r"creature|permanent|artifact|enchantment|planeswalker|nonland|battle", phrase):
                continue
            if re.search(r"\bcard\b|cards\b|graveyard", phrase) and verb != "gain control of":
                continue                                   # graveyard targets: recursion, not removal
            if not _targets_opponents(phrase):
                continue                                   # blink / polymorph your own stuff
            if verb == "return" and "hand" not in ownlow[mt.end(): mt.end() + 40] and "owner's hand" not in phrase:
                continue
            w = 0.5 if verb == "return" else 1.0
            add("targeted_interaction", w, "bounce" if verb == "return" else f"{verb} target opponent-reachable permanent")
    if re.search(r"counter target (?:\w+ )?spell", tlow):
        add("targeted_interaction", 1.0, "counterspell")
    if re.search(r"target creature (?:an opponent controls )?gets -\d+/-\d+|deals \w+ damage to target (creature|any target|planeswalker)"
                 r"|deals \d+ damage to target (?:opponent, )?creature an opponent controls", tlow):
        add("targeted_interaction", 1.0, "damage/shrink a target")
    if re.search(r"target (player|opponent) sacrifices a creature|each (other player|opponent) sacrifices a creature", tlow) and not repeat_draw:
        add("targeted_interaction", 0.5, "edict")
    if re.search(r"each player sacrifices a creature", tlow):
        add("targeted_interaction", 0.5, "symmetrical edict")
    if re.search(r"exile (target player's|each opponent's|all cards from all) graveyards?|exile all graveyards|exile target card from a graveyard", tlow):
        flags.add("graveyard_hate")
        add("targeted_interaction", 0.5, "graveyard hate")

    # ---- mass interaction: not if it only hits your own board ----
    wipe = re.search(r"(destroy|exile) all (?!lands)(other )?(?:\w+ )?(creatures|permanents|artifacts|enchantments|nonland permanents|planeswalkers)"
                     r"(?! you control)(?! you own)", tlow) \
        or re.search(r"all (?:other )?creatures get -", tlow) \
        or re.search(r"creatures your opponents control get -", tlow) \
        or re.search(r"deals \w+ damage to each (?:other )?creature", tlow) \
        or re.search(r"return all (?:\w+ )?(creatures|permanents|nonland permanents) to their owners'? hands", tlow) \
        or re.search(r"(each player|all creatures)[^.]{0,40}sacrifices? all creatures", tlow) \
        or re.search(r"sacrifices all creatures they control", tlow)
    if wipe and poly != "self":
        conditional = re.search(r"if x is (\d+) or more, (destroy|exile) all", tlow)
        add("mass_interaction", 1.0, "board wipe" + (f" (needs X >= {conditional.group(1)})" if conditional else ""))
        if not re.search(r"your opponents control|an opponent controls|creatures you don't control|except for tokens you control", tlow):
            flags.add("symmetrical_wipe")

    # ---- protection (granted to others, pillow fort) ----
    if re.search(r"(creatures|permanents|other \w+s?) you control (?:gain|have|get [^.]*and gain) [^.]*(hexproof|indestructible|shroud|protection)", tlow) \
            or re.search(r"you and (?:other )?creatures you control have [^.]*(hexproof|protection)", tlow) \
            or re.search(r"(equipped|enchanted) creature (?:gets [^.]* and )?has [^.]*(hexproof|indestructible|shroud|protection)", tlow) \
            or re.search(r"target (?:creature|permanent) you control (?:gains|phases out)", tlow) \
            or re.search(r"your commander[^.]*(hexproof|indestructible|protection|phases? out)", tlow) \
            or re.search(r"permanents you control phase out|you have hexproof", tlow):
        add("protection", 1.0, "grants protection")
    if re.search(r"creatures can't attack you(?: or (?:planeswalkers|permanents) you control)? unless", tlow) \
            or re.search(r"creatures can't attack you\b", tlow):
        add("protection", 1.0, "pillow fort: taxes or stops attacks on you")
        flags.add("pillow_fort")
    if re.search(r"counter target (spell|instant|sorcery|noncreature spell)", tlow):
        add("protection", 0.5, "counterspell (can protect)")

    # ---- tutor (non-land) ----
    for ms in SEARCH_ANY.finditer(own):
        what = ms.group(1).lower()
        if re.search(r"land|plains|island|swamp|mountain|forest|wastes", what):
            continue
        if re.search(r"named|with the same name", ownlow[ms.start(): ms.end() + 40]):
            continue
        add("tutor", 1.0, f"searches for a {what.strip() or 'card'}card")
        break

    # ---- recursion ----
    if re.search(r"(return|put) target [^.]*card from (?:your|a) graveyard (?:to|onto|into)", tlow) \
            or re.search(r"return [^.]*from your graveyard to (?:your hand|the battlefield)", tlow) \
            or re.search(r"return (?:up to \w+ )?target (?:\w+ )?cards? from your graveyard", tlow) \
            or re.search(r"choose (?:\w+ )?target creature cards? in your graveyard", tlow) \
            or re.search(r"return enchanted creature card to the battlefield", tlow) \
            or re.search(r"dies, return (?:that card|it) to the battlefield", tlow) \
            or re.search(r"puts? all cards they exiled this way onto the battlefield", tlow):
        add("recursion", 1.0, "returns cards from the graveyard")
        if "battlefield" in tlow:
            flags.add("reanimation")
    elif re.search(r"(cast|play) [^.]*from your graveyard", tlow):
        add("recursion", 0.25, "self-recursion / graveyard casting")

    # ---- tokens (fodder for polymorph / sacrifice / go-wide plans) ----
    tok = re.search(r"create (?:a|an|one|two|three|four|five|x|that many|\w+) (?:tapped )?[^.]*?creature tokens?", tlow)
    if tok:
        line = tlow[: tok.start()].rsplit("\n", 1)[-1]
        repeatable = re.search(r"\b(whenever|at the beginning)\b", line) or re.search(r"^\s*(?:\{[^}]*\},? ?)+[^:]*:|^\s*[+−-]\d+:", line) \
            or (is_land and ":" in line)
        add("tokens", 1.0 if repeatable else 0.5, "repeatable creature tokens" if repeatable else "one-shot creature tokens")

    # ---- win conditions (weak; the model and combo results refine this) ----
    if re.search(r"you win the game|loses the game", tlow):
        add("wincon", 1.0, "alternate win / loss text")
    if re.search(r"creatures you control get \+\d+/\+\d+ and gain trample", tlow):
        add("wincon", 0.5, "overrun-style finisher")
    if re.search(r"(each opponent|target player|that player) loses (?:\d+|life equal)", tlow) and re.search(r"whenever|at the beginning", tlow):
        add("wincon", 0.25, "repeatable drain")

    # ---- flags ----
    if re.search(r"sacrifice (?:a|another) (?:creature|permanent|artifact)[^:]*:", tlow):
        flags.add("sac_outlet")
    if re.search(r"destroy all lands|sacrifices? all lands|lands don't untap|each player sacrifices (?:\w+ )?lands|destroy all nonbasic lands|lands? (?:your opponents control )?don't untap", tlow):
        flags.add("mld")
    if re.search(r"takes? an extra turn|take (?:\w+ )?extra turns", ownlow):
        flags.add("extra_turn")
    if re.search(r"can't cast more than|spells? (?:your opponents cast )?cost \{\d\} more|don't untap during|can't untap|players can't search|each player can't", tlow):
        flags.add("stax")
    if card.get("game_changer"):
        flags.add("game_changer")
    if poly:
        flags.add("_poly_" + poly)     # internal marker for the tag veto; stripped from output
    return roles, flags, why


def _bucket(w: float) -> float:
    return 1.0 if w >= 0.75 else 0.5 if w >= 0.375 else 0.25 if w > 0 else 0.0


# roles a text rule can overrule: (rule condition flag, roles removed from otag signals)
def _veto(rule_roles: dict, rule_flags: set, tag_roles: dict, card: dict) -> list[str]:
    notes = []
    if "_poly_self" in rule_flags:
        for r in ("targeted_interaction", "mass_interaction"):
            if tag_roles.pop(r, None):
                notes.append(f"ignored tag {r}: polymorph exiles your own creatures")
    if "_poly_any" in rule_flags:
        if tag_roles.pop("mass_interaction", None):
            notes.append("ignored tag mass_interaction: polymorph, not a wipe")
        if tag_roles.get("targeted_interaction", 0) > 0.5:
            tag_roles["targeted_interaction"] = 0.5
    tl = card_text(card).lower()
    if "targeted_interaction" in tag_roles and "targeted_interaction" not in rule_roles:
        if "mass_interaction" in rule_roles:
            tag_roles.pop("targeted_interaction")
            notes.append("ignored tag targeted_interaction: it's the wipe (tags call wipes creature removal too)")
        elif re.search(r"ward\W+sacrifice", tl) and not re.search(r"\b(destroy|exile|counter|return) target", tl):
            tag_roles.pop("targeted_interaction")
            notes.append("ignored tag targeted_interaction: the sacrifice is a ward cost, not removal")
    if "card_advantage" in tag_roles and "card_advantage" not in rule_roles:
        if "Land" in card_type_line(card).split(" // ")[0]:
            tag_roles["card_advantage"] = 0.25
            notes.append("tag card_advantage on a land counted as 0.25 (cycling / utility)")
        elif ("_poly_self" in rule_flags or "_poly_any" in rule_flags) and "draw" not in tl:
            tag_roles.pop("card_advantage")
            notes.append("ignored tag card_advantage: polymorph swaps cards, it doesn't draw")
    if "ramp" in tag_roles and "ramp" not in rule_roles:
        tag_roles.pop("ramp")
        notes.append("ignored tag ramp: no mana or land you put into play in the card's own text")
    if "mass_interaction" in tag_roles and "mass_interaction" not in rule_roles:
        if re.search(r"all creatures you control|creatures you control", tl) and not re.search(r"opponents? control|each creature", tl):
            tag_roles.pop("mass_interaction")
            notes.append("ignored tag mass_interaction: only affects your own creatures")
    return notes


def tag_deck(deck: dict) -> dict:
    has_otags = deck.get("data", {}).get("has_otags", False)
    out_cards, review = [], []
    totals = {r: 0.0 for r in ROLES}
    for e in deck["cards"]:
        if e["board"] not in ("main", "commander"):
            continue
        card = e["card"]
        rs, flags, why = text_signals(card, e)
        os_, oflags = otag_signals(e.get("otags", []))
        flags |= oflags
        veto_notes = _veto(rs, flags, os_, card)
        roles, disagreements = {}, []
        for role in set(rs) | set(os_):
            r, o = rs.get(role, 0), os_.get(role, 0)
            if r and o:
                conf, src, w = "high", "rule+otag", max(r, o)
            elif r:
                conf = "low" if r <= 0.25 else "medium"
                src, w = "rule", r
                if has_otags and e.get("otags") and r >= 0.5 and role not in ("land", "tokens", "engine") \
                        and why.get(role) != "counterspell (can protect)":
                    disagreements.append(f"rule says {role} ({why.get(role)}), otags don't")
            else:
                conf, src, w = "medium", "otag", o
                if role not in ("land", "tokens"):
                    disagreements.append(f"otag says {role}, no text rule fired")
            roles[role] = {"weight": w if role == "land" else _bucket(w), "confidence": conf, "source": src,
                           **({"why": why[role]} if role in why else {})}
        ranked = sorted(roles.items(), key=lambda kv: (kv[0] != "land", -kv[1]["weight"],
                                                        {"high": 0, "medium": 1, "low": 2}[kv[1]["confidence"]]))
        dropped = [k for k, _ in ranked[3:]]
        roles = dict(ranked[:3])
        reason = None
        is_land_only = list(roles) == ["land"]
        if not roles:
            reason = "no role detected - decide: engine/synergy for this commander, wincon, or off-plan"
        elif disagreements:
            reason = "; ".join(disagreements)
        elif all(v["confidence"] == "low" for v in roles.values()):
            reason = "only weak signals"
        if dropped:
            reason = ((reason + "; ") if reason else "") + f"more than 3 roles, dropped {dropped}"
        rec = {"name": e["name"], "qty": e["qty"], "board": e["board"], "cmc": card.get("cmc", 0),
               "type_line": card_type_line(card), "roles": roles,
               "flags": sorted(f for f in flags if not f.startswith("_"))}
        if veto_notes:
            rec["tag_vetoes"] = veto_notes
        front_is_land = "land" in roles and roles["land"]["weight"] == 1.0
        if reason and not is_land_only and not front_is_land and e["board"] != "commander":
            rec["needs_review"] = reason
            review.append({"name": e["name"], "reason": reason, "type_line": card_type_line(card),
                           "oracle_text": card_text(card)[:600]})
        out_cards.append(rec)
        if e["board"] == "main":
            for role, v in roles.items():
                totals[role] += v["weight"] * e["qty"]
    return {"schema": "edh-roles/1", "has_otags": has_otags, "cards": out_cards,
            "totals": {k: round(v, 2) for k, v in totals.items()}, "needs_review": review}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck")
    ap.add_argument("-o", "--out", default="roles.json")
    a = ap.parse_args()
    res = tag_deck(load_json(a.deck))
    dump_json(res, a.out)
    print("Weighted role totals (main deck): " + ", ".join(f"{k}={v:g}" for k, v in res["totals"].items()),
          file=sys.stderr)
    print(f"{len(res['needs_review'])} card(s) need model review", file=sys.stderr)


if __name__ == "__main__":
    main()
