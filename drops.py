# 🎁 Monitored drops: whatever from here drops shows up in a temporary banner on the screen and in a marker on the map

# How long the banner stays on the screen (seconds)
DROP_ALERT_SECONDS = 4

# Speaks the name of the item that dropped (Windows voice, no internet), instead of the "ting"
DROP_SPEAK = True

# Part of the voice name: "Zira" (English, like the item names) or "Maria" (pt-BR). Without that voice, the Windows
# default is used
DROP_SPEECH_VOICE = "Zira"

# Speech rate, from -10 to 10
DROP_SPEECH_RATE = 1

# Plays a "ting" when a monitored item drops (only with DROP_SPEAK = False)
DROP_PLAY_SOUND = True

# Prints every new item on the ground (txt, quality, flags). To find an item's txt: drop it on the ground and read the log
DROP_LOG_ALL = False

# Monitored runes: from this one up, in game order (Pul, Um, Mal... Zod). None turns it off.
# They get a banner and sound, and on the map the drop marker instead of the rune one. The others stay only in
# RUNES_TO_SHOW
DROP_RUNES_FROM = "Thul"

# Each rule needs "name" (the alert text) and "txt" (the item's dwTxtFileNo). Optional filters, combined with AND:
#   "quality":   list with inferior, normal, superior, magic, set, rare, unique, crafted, tempered
#   "ethereal":  True or False
#   "socketed":  True or False (whether it has sockets, not how many)
#   "sockets":   exact number of sockets, from 1 to 6 (item stat 194; see fabiomh/game/drops.py)
#   "unique_id": the unique or set id (dwUniqueOrSetId, also in the log)
# Example: {"name": "Eth piece", "txt": 0, "quality": ["superior", "unique"], "ethereal": True, "socketed": True}
# "enabled": False turns the rule off without removing it from the list (without that key, it stays on)
DROP_RULES = [
    {"name": "Wirt's Leg", "txt": 88, "enabled": False},  # no filters: any variant

    # Sigon's Complete Steel set. Only the "set" quality: no other set uses these bases.
    # To check: public txt (armor.txt), not measured in this version. See DROP_LOG_ALL above
    {"name": "Sigon's Visor", "txt": 310, "quality": ["set"]},    # Great Helm
    {"name": "Sigon's Shelter", "txt": 324, "quality": ["set"]},  # Gothic Plate
    {"name": "Sigon's Guard", "txt": 332, "quality": ["set"]},    # Tower Shield
    {"name": "Sigon's Gage", "txt": 338, "quality": ["set"]},     # Gauntlets
    {"name": "Sigon's Sabot", "txt": 343, "quality": ["set"]},    # Greaves
    {"name": "Sigon's Wrap", "txt": 348, "quality": ["set"]},     # Plated Belt

    # Blue (magic) and unique charms. To check: public txt (cm1 = 603, cm3 = 605) + 15, like the keys below.
    # Not measured in this version. See DROP_LOG_ALL above
    {"name": "Small Charm", "txt": 618, "quality": ["magic"]},
    {"name": "Annihilus", "txt": 618, "quality": ["unique"]},           # the only unique Small Charm
    {"name": "Grand Charm", "txt": 620, "quality": ["magic"]},
    {"name": "Unique Grand Charm", "txt": 620, "quality": ["unique"]},  # Gheed's, Torch, Sunder

    # Pandemonium keys. To check: public txt (647 to 649) + 15, the shift measured on the runes (El 610 → 625).
    # Not measured in this version. See DROP_LOG_ALL above
    {"name": "Key of Terror", "txt": 662},
    {"name": "Key of Hate", "txt": 663},
    {"name": "Key of Destruction", "txt": 664},

    # Runeword bases (Infinity, Insight): elite polearms with 4 sockets, normal or superior. The Ogre Axe does not
    # reach 4. Measured in game: a 4os Cryptic Axe alerted as "Thresher 4os" (txt 256) and a 4os Colossus Voulge
    # did not alert, i.e. the old txt (255 to 259) were 1 too high. The ids are in sequence in weapons.txt, so they all
    # go down by 1 (measured Colossus Voulge = 254 and Cryptic Axe = 256; the others by order). The 4-socket filter
    # worked on both
    {"name": "Colossus Voulge 4os", "txt": 254, "quality": ["normal", "superior"], "sockets": 4},
    {"name": "Thresher 4os", "txt": 255, "quality": ["normal", "superior"], "sockets": 4},
    {"name": "Cryptic Axe 4os", "txt": 256, "quality": ["normal", "superior"], "sockets": 4},
    {"name": "Great Poleaxe 4os", "txt": 257, "quality": ["normal", "superior"], "sockets": 4},
    {"name": "Giant Thresher 4os", "txt": 258, "quality": ["normal", "superior"], "sockets": 4},

    # Valuable uniques. Each base has a single unique, so txt + "unique" already identifies the item (no unique_id).
    # To check: public armor.txt txt (the same as Sigon's above), not measured in this version. See DROP_LOG_ALL above
    # Expensive
    {"name": "Griffon's Eye", "txt": 421, "quality": ["unique"]},        # Diadem
    {"name": "Tyrael's Might", "txt": 442, "quality": ["unique"]},       # Sacred Armor
    {"name": "Crown of Ages", "txt": 427, "quality": ["unique"]},        # Corona
    {"name": "Arachnid Mesh", "txt": 460, "quality": ["unique"]},        # Spiderweb Sash
    {"name": "Andariel's Visage", "txt": 428, "quality": ["unique"]},    # Demonhead
    {"name": "Dracul's Grasp", "txt": 451, "quality": ["unique"]},       # Vampirebone Gloves
    {"name": "Hellfire Torch", "txt": 619, "quality": ["unique"]},       # Large Charm (cm2 = 604 + 15, like the charms)
    # Weapons: txt estimated by counting the public weapons.txt. The same count got the polearms above right (the
    # measured Cryptic Axe gave 256), so they are probably right. Disabled until measured with DROP_LOG_ALL
    {"name": "Grandfather", "txt": 234, "quality": ["unique"], "enabled": False},      # Colossus Blade
    {"name": "Windforce", "txt": 271, "quality": ["unique"], "enabled": False},        # Hydra Bow
    {"name": "Death's Fathom", "txt": 290, "quality": ["unique"], "enabled": False},   # Dimensional Shard
    # Good ones, easy to sell
    {"name": "Shako", "txt": 422, "quality": ["unique"]},                # Harlequin Crest
    {"name": "Verdungo's", "txt": 462, "quality": ["unique"]},           # Mithril Coil
    {"name": "Stormshield", "txt": 447, "quality": ["unique"]},          # Monarch
    {"name": "Monarch Blue", "txt": 447, "quality": ["magic"]},          # same base as Stormshield, magic (blue)
    {"name": "Monarch 4os", "txt": 447, "quality": ["normal", "superior"], "sockets": 4},  # runeword base (Spirit)
    {"name": "Herald of Zakarum", "txt": 481, "quality": ["unique"]},    # Gilded Shield
    {"name": "Nightwing's Veil", "txt": 426, "quality": ["unique"]},     # Spired Helm
    {"name": "Shadow Dancer", "txt": 459, "quality": ["unique"]},        # Myrmidon Greaves
    {"name": "Sandstorm Trek", "txt": 456, "quality": ["unique"]},       # Scarabshell Boots
    {"name": "Marrowwalk", "txt": 457, "quality": ["unique"]},           # Boneweave Boots
    {"name": "War Traveler", "txt": 388, "quality": ["unique"]},         # Battle Boots
    {"name": "Thundergod's Vigor", "txt": 394, "quality": ["unique"]},   # War Belt
    {"name": "Nosferatu's Coil", "txt": 461, "quality": ["unique"]},     # Vampirefang Belt
    {"name": "Steelrend", "txt": 454, "quality": ["unique"]},            # Ogre Gauntlets
    {"name": "Arkaine's Valor", "txt": 437, "quality": ["unique"]},      # Balrog Skin
    {"name": "Leviathan", "txt": 439, "quality": ["unique"]},            # Kraken Shell
    {"name": "Vipermagi", "txt": 360, "quality": ["unique"]},            # Serpentskin Armor
    {"name": "Kira's Guardian", "txt": 420, "quality": ["unique"]},      # Tiara
    {"name": "Vampire Gaze", "txt": 395, "quality": ["unique"]},         # Grim Helm
    # Jewelry: the base is the same for all unique rings and amulets (SoJ, BK, Mara's, Highlord's... and the cheap ones).
    # With the unique_id from the log, you can keep only the expensive ones. Public txt (rin 522, amu 520) + 15, like
    # the charms
    {"name": "Unique Ring", "txt": 537, "quality": ["unique"]},
    {"name": "Unique Amulet", "txt": 535, "quality": ["unique"]},

    # Valuable sets. None of these bases is used by another set item, so txt + "set" already identifies the piece; the
    # ones that also have a unique are told apart by "quality". To check: public armor.txt txt (same count as the
    # uniques above), not measured in this version. See DROP_LOG_ALL above
    # Tal Rasha's Wrappings
    {"name": "Tal Rasha's Guardianship", "txt": 440, "quality": ["set"]},  # Lacquered Plate
    {"name": "Tal Rasha's Horadric Crest", "txt": 358, "quality": ["set"]},  # Death Mask
    {"name": "Tal Rasha's Fine-Spun Cloth", "txt": 392, "quality": ["set"]},  # Mesh Belt
    # Weapon: txt estimated by counting weapons.txt (like Death's Fathom above). Disabled until measured
    {"name": "Tal Rasha's Lidless Eye", "txt": 285, "quality": ["set"], "enabled": False},  # Swirling Crystal
    # Tal Rasha's Adjudication is an amulet: the base (535) is the same as all set amulets. To monitor it, read the
    # unique_id in the log and add {"txt": 535, "quality": ["set"], "unique_id": ...}
    # Orphan's Call
    {"name": "Guillaume's Face", "txt": 356, "quality": ["set"]},        # Winged Helm
    {"name": "Wilhelm's Pride", "txt": 393, "quality": ["set"]},         # Battle Belt
    {"name": "Magnus' Skin", "txt": 381, "quality": ["set"]},            # Sharkskin Gloves
    {"name": "Whitstan's Guard", "txt": 375, "quality": ["set"]},        # Round Shield
]
