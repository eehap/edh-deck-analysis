#!/usr/bin/env python3
"""Build offline test fixtures (tag slugs follow the real Scryfall Oracle Tags names; "recursion-any-card" is illustrative): a Scryfall-shaped oracle-cards file, an oracle-tags file,
a Meren decklist, and a canned Spellbook response. Dev only; not packaged."""
import json
import sys
import uuid
from pathlib import Path

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "fixtures")
OUT.mkdir(parents=True, exist_ok=True)

def oid(name): return str(uuid.uuid5(uuid.NAMESPACE_URL, "oracle:" + name))

# name, cost, cmc, type, text, identity, produced, gc, price, extra
C = []
def card(name, cost, cmc, type_line, text, ci, produced=None, gc=False, price="0.50", **kw):
    d = {"object": "card", "oracle_id": oid(name), "name": name, "layout": kw.pop("layout", "normal"),
         "mana_cost": cost, "cmc": float(cmc), "type_line": type_line, "oracle_text": text,
         "colors": [c for c in "WUBRG" if "{" + c + "}" in (cost or "")], "color_identity": list(ci),
         "keywords": kw.pop("keywords", []), "legalities": {"commander": kw.pop("legal", "legal")},
         "game_changer": gc, "edhrec_rank": kw.pop("rank", 500), "reserved": False, "digital": False,
         "rarity": kw.pop("rarity", "rare"), "games": ["paper", "mtgo"],
         "prices": {"usd": price, "usd_foil": None, "eur": None, "tix": None}}
    if produced: d["produced_mana"] = produced
    d.update(kw)
    C.append(d)

B, G, BG = "B", "G", "BG"
card("Meren of Clan Nel Toth", "{2}{B}{G}", 4, "Legendary Creature — Human Shaman", "Whenever another creature you control dies, you get an experience counter.\nAt the beginning of your end step, choose target creature card in your graveyard. If that card's mana value is less than or equal to the number of experience counters you have, return that card to the battlefield. Otherwise, put it into your hand.", BG, rarity="mythic")
# ramp
card("Sol Ring", "{1}", 1, "Artifact", "{T}: Add {C}{C}.", "", ["C"], price="1.50", rank=1)
card("Arcane Signet", "{2}", 2, "Artifact", "{T}: Add one mana of any color in your commander's color identity.", "", ["W","U","B","R","G"])
card("Golgari Signet", "{2}", 2, "Artifact", "{1}, {T}: Add {B}{G}.", BG, ["B","G"])
card("Cultivate", "{2}{G}", 3, "Sorcery", "Search your library for up to two basic land cards, reveal those cards, put one onto the battlefield tapped and the other into your hand, then shuffle.", G)
card("Kodama's Reach", "{2}{G}", 3, "Sorcery — Arcane", "Search your library for up to two basic land cards, reveal those cards, put one onto the battlefield tapped and the other into your hand, then shuffle.", G)
card("Farseek", "{1}{G}", 2, "Sorcery", "Search your library for a Plains, Island, Swamp, or Mountain card, put it onto the battlefield tapped, then shuffle.", G)
card("Llanowar Elves", "{G}", 1, "Creature — Elf Druid", "{T}: Add {G}.", G, ["G"])
card("Birds of Paradise", "{G}", 1, "Creature — Bird", "Flying\n{T}: Add one mana of any color.", G, ["W","U","B","R","G"])
card("Sakura-Tribe Elder", "{1}{G}", 2, "Creature — Snake Shaman", "Sacrifice Sakura-Tribe Elder: Search your library for a basic land card, put that card onto the battlefield tapped, then shuffle.", G)
card("Wood Elves", "{2}{G}", 3, "Creature — Elf Scout", "When Wood Elves enters, search your library for a Forest card, put that card onto the battlefield, then shuffle.", G)
card("Burnished Hart", "{3}", 3, "Artifact Creature — Elk", "{3}, Sacrifice Burnished Hart: Search your library for up to two basic land cards, put them onto the battlefield tapped, then shuffle.", "")
card("Thran Dynamo", "{4}", 4, "Artifact", "{T}: Add {C}{C}{C}.", "", ["C"], price="5.00")
card("Gilded Lotus", "{5}", 5, "Artifact", "{T}: Add three mana of any one color.", "", ["W","U","B","R","G"])
# draw
card("Skullclamp", "{1}", 1, "Artifact — Equipment", "Equipped creature gets +1/-1.\nWhenever equipped creature dies, draw two cards.\nEquip {1}", "")
card("Phyrexian Arena", "{1}{B}{B}", 3, "Enchantment", "At the beginning of your upkeep, you draw a card and you lose 1 life.", B)
card("Harvester of Souls", "{4}{B}{B}", 6, "Creature — Demon", "Deathtouch\nWhenever another nontoken creature dies, you may draw a card.", B)
card("Night's Whisper", "{1}{B}", 2, "Sorcery", "You draw two cards and you lose 2 life.", B)
card("Grim Haruspex", "{2}{B}", 3, "Creature — Human Wizard", "Morph {B}\nWhenever another nontoken creature you control dies, draw a card.", B)
card("Beast Whisperer", "{2}{G}{G}", 4, "Creature — Elf Druid", "Whenever you cast a creature spell, draw a card.", G)
card("Midnight Reaper", "{2}{B}", 3, "Creature — Zombie Knight", "Whenever a nontoken creature you control dies, Midnight Reaper deals 1 damage to you and you draw a card.", B)
card("Sign in Blood", "{B}{B}", 2, "Sorcery", "Target player draws two cards and loses 2 life.", B)
card("Pelakka Wurm", "{4}{G}{G}{G}", 7, "Creature — Wurm", "Trample\nWhen Pelakka Wurm enters, you gain 7 life.\nWhen Pelakka Wurm dies, draw a card.", G, keywords=["Trample"])
card("Sylvan Library", "{1}{G}", 2, "Enchantment", "At the beginning of your draw step, you may draw two additional cards. If you do, choose two cards in your hand drawn this turn. For each of those cards, pay 4 life or put the card on top of your library.", G, price="30.00")
# removal
card("Assassin's Trophy", "{B}{G}", 2, "Instant", "Destroy target permanent an opponent controls. Its controller may search their library for a basic land card, put it onto the battlefield, then shuffle.", BG)
card("Beast Within", "{2}{G}", 3, "Instant", "Destroy target permanent. Its controller creates a 3/3 green Beast creature token.", G)
card("Putrefy", "{1}{B}{G}", 3, "Instant", "Destroy target artifact or creature. It can't be regenerated.", BG)
card("Go for the Throat", "{1}{B}", 2, "Instant", "Destroy target nonartifact creature.", B)
card("Reclamation Sage", "{2}{G}", 3, "Creature — Elf Shaman", "When Reclamation Sage enters, you may destroy target artifact or enchantment.", G)
card("Ravenous Chupacabra", "{2}{B}{B}", 4, "Creature — Horror", "When Ravenous Chupacabra enters, destroy target creature an opponent controls.", B)
card("Feed the Swarm", "{1}{B}", 2, "Sorcery", "Choose one —\n• Destroy target creature or enchantment an opponent controls.\n• Destroy target artifact an opponent controls.\nYou lose life equal to that permanent's mana value.", B)
# wipes
card("Damnation", "{2}{B}{B}", 4, "Sorcery", "Destroy all creatures. They can't be regenerated.", B, price="20.00")
card("Toxic Deluge", "{2}{B}", 3, "Sorcery", "As an additional cost to cast this spell, pay X life.\nAll creatures get -X/-X until end of turn.", B, price="12.00")
card("Living Death", "{3}{B}{B}", 5, "Sorcery", "Each player exiles all creature cards from their graveyard, then sacrifices all creatures they control, then puts all cards they exiled this way onto the battlefield.", B)
# protection
card("Heroic Intervention", "{1}{G}", 2, "Instant", "Permanents you control gain hexproof and indestructible until end of turn.", G)
card("Swiftfoot Boots", "{2}", 2, "Artifact — Equipment", "Equipped creature has hexproof and haste.\nEquip {1}", "")
card("Lightning Greaves", "{2}", 2, "Artifact — Equipment", "Equipped creature has haste and shroud.\nEquip {0}", "")
# tutors
card("Demonic Tutor", "{1}{B}", 2, "Sorcery", "Search your library for a card, put that card into your hand, then shuffle.", B, gc=True, price="25.00")
card("Worldly Tutor", "{G}", 1, "Instant", "Search your library for a creature card, reveal it, then shuffle and put the card on top.", G, gc=True, price="15.00")
card("Diabolic Intent", "{1}{B}", 2, "Sorcery", "As an additional cost to cast this spell, sacrifice a creature.\nSearch your library for a card, put that card into your hand, then shuffle.", B)
card("Survival of the Fittest", "{1}{G}", 2, "Enchantment", "{G}, Discard a creature card: Search your library for a creature card, reveal it, put it into your hand, then shuffle.", G, gc=True, price="20.00")
# recursion
card("Reanimate", "{B}", 1, "Sorcery", "Put target creature card from a graveyard onto the battlefield under your control. You lose life equal to its mana value.", B)
card("Eternal Witness", "{1}{G}{G}", 3, "Creature — Human Shaman", "When Eternal Witness enters, return target card from your graveyard to your hand.", G)
card("Animate Dead", "{1}{B}", 2, "Enchantment — Aura", "Enchant creature card in a graveyard\nWhen Animate Dead enters, if it's on the battlefield, it loses \"enchant creature card in a graveyard\" and gains \"enchant creature put onto the battlefield with Animate Dead.\" Return enchanted creature card to the battlefield under your control and attach Animate Dead to it. When Animate Dead leaves the battlefield, that creature's controller sacrifices it.\nEnchanted creature gets -1/-0.", B)
card("Victimize", "{2}{B}", 3, "Sorcery", "Choose two target creature cards in your graveyard. Sacrifice a creature, then return the chosen cards to the battlefield tapped.", B)
card("Dread Return", "{2}{B}{B}", 4, "Sorcery", "Return target creature card from your graveyard to the battlefield.\nFlashback—Sacrifice three creatures.", B)
# plan
card("Viscera Seer", "{B}", 1, "Creature — Vampire Wizard", "Sacrifice a creature: Scry 1.", B)
card("Ashnod's Altar", "{3}", 3, "Artifact", "Sacrifice a creature: Add {C}{C}.", "", ["C"], price="8.00")
card("Phyrexian Altar", "{3}", 3, "Artifact", "Sacrifice a creature: Add one mana of any color.", "", ["W","U","B","R","G"], price="40.00")
card("Blood Artist", "{1}{B}", 2, "Creature — Vampire", "Whenever Blood Artist or another creature dies, target player loses 1 life and you gain 1 life.", B)
card("Zulaport Cutthroat", "{1}{B}", 2, "Creature — Human Rogue Ally", "Whenever Zulaport Cutthroat or another creature you control dies, each opponent loses 1 life and you gain 1 life.", B)
card("Mikaeus, the Unhallowed", "{3}{B}{B}{B}", 6, "Legendary Creature — Zombie Cleric", "Intimidate\nWhenever a Human deals damage to you, destroy it.\nOther non-Human creatures you control get +1/+1 and have undying.", B, rarity="mythic", keywords=["Intimidate"])
card("Triskelion", "{6}", 6, "Artifact Creature — Construct", "Triskelion enters with three +1/+1 counters on it.\nRemove a +1/+1 counter from Triskelion: It deals 1 damage to any target.", "")
card("Gravecrawler", "{B}", 1, "Creature — Zombie", "Gravecrawler can't block.\nYou may cast Gravecrawler from your graveyard as long as you control a Zombie.", B)
card("Grave Pact", "{1}{B}{B}{B}", 4, "Enchantment", "Whenever a creature you control dies, each other player sacrifices a creature.", B, price="10.00")
card("Massacre Wurm", "{3}{B}{B}{B}", 6, "Creature — Phyrexian Wurm", "When Massacre Wurm enters, creatures your opponents control get -2/-2 until end of turn.\nWhenever a creature an opponent controls dies, that player loses 2 life.", B)
card("Spore Frog", "{G}", 1, "Creature — Frog", "Sacrifice Spore Frog: Prevent all combat damage that would be dealt this turn.", G)
card("Plaguecrafter", "{2}{B}", 3, "Creature — Human Shaman", "When Plaguecrafter enters, each player sacrifices a creature or planeswalker of their choice. Each player who can't discards a card.", B)
card("Fleshbag Marauder", "{2}{B}", 3, "Creature — Phyrexian Zombie Warrior", "When Fleshbag Marauder enters, each player sacrifices a creature of their choice.", B)
card("Overrun", "{2}{G}{G}{G}", 5, "Sorcery", "Creatures you control get +3/+3 and gain trample until end of turn.", G)
card("Darksteel Colossus", "{11}", 11, "Artifact Creature — Golem", "Trample, indestructible\nIf Darksteel Colossus would be put into a graveyard from anywhere, reveal Darksteel Colossus and shuffle it into its owner's library instead.", "", keywords=["Trample", "Indestructible"])
card("Pitiless Plunderer", "{3}{B}", 4, "Creature — Human Pirate", "Whenever another creature you control dies, create a Treasure token.", B)
card("Yawgmoth, Thran Physician", "{2}{B}{B}", 4, "Legendary Creature — Human Cleric", "Protection from Humans\nPay 1 life, Sacrifice another creature: Put a -1/-1 counter on up to one target creature and draw a card.\n{B}{B}, Discard a card: Proliferate.", B, rarity="mythic", price="35.00")
# MDFC
C.append({"object": "card", "oracle_id": oid("Bala Ged Recovery"), "name": "Bala Ged Recovery // Bala Ged Sanctuary",
          "layout": "modal_dfc", "cmc": 3.0, "color_identity": ["G"], "colors": ["G"], "keywords": [],
          "legalities": {"commander": "legal"}, "game_changer": False, "edhrec_rank": 900, "rarity": "uncommon",
          "digital": False, "reserved": False, "games": ["paper"], "produced_mana": ["G"],
          "prices": {"usd": "0.40"}, "type_line": "Sorcery // Land",
          "card_faces": [{"name": "Bala Ged Recovery", "mana_cost": "{2}{G}", "type_line": "Sorcery",
                          "oracle_text": "Return target card from your graveyard to your hand.", "colors": ["G"]},
                         {"name": "Bala Ged Sanctuary", "mana_cost": "", "type_line": "Land",
                          "oracle_text": "Bala Ged Sanctuary enters tapped.\n{T}: Add {G}.", "colors": []}]})
# lands
card("Command Tower", "", 0, "Land", "{T}: Add one mana of any color in your commander's color identity.", "", ["W","U","B","R","G"], rarity="common")
card("Overgrown Tomb", "", 0, "Land — Swamp Forest", "({T}: Add {B} or {G}.)\nAs Overgrown Tomb enters, you may pay 2 life. If you don't, it enters tapped.", BG, ["B","G"], price="15.00")
card("Llanowar Wastes", "", 0, "Land", "{T}: Add {C}.\n{T}: Add {B} or {G}. Llanowar Wastes deals 1 damage to you.", BG, ["C","B","G"])
card("Woodland Cemetery", "", 0, "Land", "Woodland Cemetery enters tapped unless you control a Swamp or a Forest.\n{T}: Add {B} or {G}.", BG, ["B","G"])
card("Golgari Rot Farm", "", 0, "Land", "Golgari Rot Farm enters tapped.\nWhen Golgari Rot Farm enters, return a land you control to its owner's hand.\n{T}: Add {B}{G}.", BG, ["B","G"], rarity="common")
card("Jungle Hollow", "", 0, "Land", "Jungle Hollow enters tapped.\nWhen Jungle Hollow enters, you gain 1 life.\n{T}: Add {B} or {G}.", BG, ["B","G"], rarity="common")
card("Reliquary Tower", "", 0, "Land", "You have no maximum hand size.\n{T}: Add {C}.", "", ["C"])
card("Verdant Catacombs", "", 0, "Land", "{T}, Pay 1 life, Sacrifice Verdant Catacombs: Search your library for a Swamp or Forest card, put it onto the battlefield, then shuffle.", "", None, price="20.00")
card("Evolving Wilds", "", 0, "Land", "{T}, Sacrifice Evolving Wilds: Search your library for a basic land card, put it onto the battlefield tapped, then shuffle.", "", None, rarity="common")
card("Bojuka Bog", "", 0, "Land", "Bojuka Bog enters tapped.\nWhen Bojuka Bog enters, exile target player's graveyard.\n{T}: Add {B}.", B, ["B"], rarity="common")
card("Swamp", "", 0, "Basic Land — Swamp", "({T}: Add {B}.)", B, ["B"], rarity="common", price="0.05")
card("Forest", "", 0, "Basic Land — Forest", "({T}: Add {G}.)", G, ["G"], rarity="common", price="0.05")
# candidates (not in deck) for cut/add tests
card("Fatal Push", "{B}", 1, "Instant", "Destroy target creature if it has mana value 2 or less.\nRevolt — Destroy that creature instead if it has mana value 4 or less if a permanent you controlled left the battlefield this turn.", B)
card("Deadly Rollick", "{3}{B}", 4, "Instant", "If you control a commander, you may cast this spell without paying its mana cost.\nExile target creature.", B)
card("Rampant Growth", "{1}{G}", 2, "Sorcery", "Search your library for a basic land card, put that card onto the battlefield tapped, then shuffle.", G, rarity="common")
card("Armageddon", "{3}{W}", 4, "Sorcery", "Destroy all lands.", "W")
card("Nim Deathmantle", "{2}", 2, "Artifact — Equipment", "Equipped creature gets +2/+2, has intimidate, and is a black Zombie.\nWhenever a nontoken creature is put into your graveyard from the battlefield, you may pay {4}. If you do, return that card to the battlefield and attach Nim Deathmantle to it.\nEquip {4}", "", price="3.00")
card("Time Warp", "{3}{U}{U}", 5, "Sorcery", "Target player takes an extra turn after this one.", "U")

(OUT / "oracle-cards.json").write_text(json.dumps(C, indent=1))

# oracle tags fixture (tag objects w/ parent hierarchy)
tags = []
def tag(slug, parents=(), cards=()):
    tags.append({"object": "tag", "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "tag:" + slug)), "slug": slug,
                 "label": slug, "parent_ids": [str(uuid.uuid5(uuid.NAMESPACE_URL, "tag:" + p)) for p in parents],
                 "taggings": [{"oracle_id": oid(c)} for c in cards]})
tag("ramp"); tag("mana-rock", ["ramp"], ["Sol Ring", "Arcane Signet", "Golgari Signet", "Thran Dynamo", "Gilded Lotus"])
tag("mana-dork", ["ramp"], ["Llanowar Elves", "Birds of Paradise"])
tag("land-ramp", ["ramp"], ["Cultivate", "Kodama's Reach", "Farseek", "Sakura-Tribe Elder", "Wood Elves", "Burnished Hart", "Rampant Growth"])
tag("draw"); tag("card-advantage", [], ["Phyrexian Arena", "Harvester of Souls", "Grim Haruspex", "Skullclamp", "Sylvan Library"])
tag("repeatable-draw", ["draw"], ["Phyrexian Arena", "Harvester of Souls", "Grim Haruspex", "Beast Whisperer", "Midnight Reaper", "Skullclamp", "Yawgmoth, Thran Physician"])
tag("burst-draw", ["draw"], ["Night's Whisper", "Sign in Blood"])
tag("removal"); tag("spot-removal", ["removal"], ["Go for the Throat", "Putrefy", "Ravenous Chupacabra", "Fatal Push", "Deadly Rollick"])
tag("removal-permanent", ["removal"], ["Assassin's Trophy", "Beast Within"])
tag("removal-artifact", ["removal"], ["Reclamation Sage", "Putrefy"])
tag("sweeper", [], ["Damnation", "Toxic Deluge", "Living Death"]); tag("board-wipe", [], ["Damnation", "Toxic Deluge"])
tag("gives-hexproof", [], ["Heroic Intervention", "Swiftfoot Boots"]); tag("gives-shroud", [], ["Lightning Greaves"]); tag("gives-indestructible", [], ["Heroic Intervention"])
tag("tutor"); tag("tutor-any-card", ["tutor"], ["Demonic Tutor", "Diabolic Intent"])
tag("tutor-creature", ["tutor"], ["Worldly Tutor", "Survival of the Fittest"])
tag("recursion-any-card", [], ["Eternal Witness", "Bala Ged Recovery"]); tag("reanimate-creature", [], ["Reanimate", "Animate Dead", "Victimize", "Dread Return", "Meren of Clan Nel Toth"]); tag("mass-reanimation", [], ["Living Death"])
tag("sacrifice-outlet", [], ["Viscera Seer", "Ashnod's Altar", "Phyrexian Altar", "Yawgmoth, Thran Physician"])
tag("death-trigger", [], ["Blood Artist", "Zulaport Cutthroat", "Grave Pact", "Midnight Reaper"]); tag("edict", [], ["Grave Pact", "Plaguecrafter", "Fleshbag Marauder"])
tag("graveyard-hate", [], ["Bojuka Bog"])
tag("land-destruction", [], ["Armageddon"]); tag("extra-turn", [], ["Time Warp"])
(OUT / "oracle-tags.json").write_text(json.dumps({"object": "list", "data": tags}, indent=1))

deck = """Commander
1 Meren of Clan Nel Toth

Deck
""" + "\n".join("1 " + n for n in [
 "Sol Ring","Arcane Signet","Golgari Signet","Cultivate","Kodama's Reach","Farseek","Llanowar Elves","Birds of Paradise",
 "Sakura-Tribe Elder","Wood Elves","Burnished Hart","Thran Dynamo","Gilded Lotus","Skullclamp","Phyrexian Arena",
 "Harvester of Souls","Night's Whisper","Grim Haruspex","Beast Whisperer","Midnight Reaper","Sign in Blood","Pelakka Wurm",
 "Sylvan Library","Assassin's Trophy","Beast Within","Putrefy","Go for the Throat","Reclamation Sage","Ravenous Chupacabra",
 "Feed the Swarm","Damnation","Toxic Deluge","Living Death","Heroic Intervention","Swiftfoot Boots","Lightning Greaves",
 "Demonic Tutor","Worldly Tutor","Diabolic Intent","Survival of the Fittest","Reanimate","Eternal Witness","Animate Dead",
 "Victimize","Dread Return","Viscera Seer","Ashnod's Altar","Phyrexian Altar","Blood Artist","Zulaport Cutthroat",
 "Mikaeus, the Unhallowed","Triskelion","Gravecrawler","Grave Pact","Massacre Wurm","Spore Frog","Plaguecrafter",
 "Fleshbag Marauder","Overrun","Darksteel Colossus","Pitiless Plunderer","Yawgmoth, Thran Physician",
 "Bala Ged Recovery","Command Tower","Overgrown Tomb","Llanowar Wastes","Woodland Cemetery","Golgari Rot Farm",
 "Jungle Hollow","Reliquary Tower","Verdant Catacombs","Evolving Wilds","Bojuka Bog"]) + "\n13 Swamp\n13 Forest\n"
(OUT / "meren.txt").write_text(deck)

def use(n): return {"card": {"name": n, "oracleId": oid(n)}, "quantity": 1, "zoneLocations": ["B"]}
spellbook = {"results": {"identity": "BG",
  "included": [
    {"id": "1234-5678", "uses": [use("Mikaeus, the Unhallowed"), use("Triskelion")],
     "produces": [{"feature": {"name": "Infinite damage"}}, {"feature": {"name": "Infinite death triggers"}}],
     "bracketTag": "S", "manaNeeded": "", "identity": "B", "legalities": {"commander": True}, "popularity": 4100,
     "easyPrerequisites": "All permanents on the battlefield.", "notablePrerequisites": "",
     "description": "1. Remove a +1/+1 counter from Triskelion to deal 1 damage, three times.\n2. Triskelion dies and returns with undying.\n3. Repeat."},
    {"id": "2345-6789", "uses": [use("Gravecrawler"), use("Phyrexian Altar"), use("Blood Artist")],
     "produces": [{"feature": {"name": "Infinite death triggers"}}, {"feature": {"name": "Infinite lifeloss"}}],
     "bracketTag": "R", "manaNeeded": "", "identity": "B", "legalities": {"commander": True}, "popularity": 9000,
     "easyPrerequisites": "Gravecrawler in graveyard, another Zombie on the battlefield.", "notablePrerequisites": "",
     "description": "1. Sacrifice Gravecrawler to Phyrexian Altar for {B}.\n2. Cast Gravecrawler from graveyard.\n3. Repeat."}],
  "almostIncluded": [
    {"id": "3456-7890", "uses": [use("Ashnod's Altar"), use("Nim Deathmantle"), use("Pitiless Plunderer")],
     "produces": [{"feature": {"name": "Infinite death triggers"}}, {"feature": {"name": "Infinite colorless mana"}}],
     "bracketTag": "R", "manaNeeded": "{4}", "identity": "B", "legalities": {"commander": True}, "popularity": 3200,
     "easyPrerequisites": "", "notablePrerequisites": "A nontoken creature", "description": "..."}],
  "almostIncludedByAddingColors": [], "includedByChangingCommanders": []}}
(OUT / "spellbook_meren.json").write_text(json.dumps(spellbook, indent=1))
print(f"wrote {len(C)} cards, {len(tags)} tags to {OUT}")
