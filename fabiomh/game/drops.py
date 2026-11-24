"""Drop tracker: alerts when an item from the rules in drops.py (root) shows up on the ground.

- "Dropped" means "seen on the ground for the first time": the table only carries the nearby rooms, so a far-away drop
  is only alerted when the player gets near. An item dropped by the player themselves also alerts (on the ground,
  dwOwnerId is always ownerless).
- Each dwUnitId alerts once per game. The seen ones reset when the seed changes or after GAME_GONE_SECONDS in a row
  without a player. The seed alone is not enough: in single player it repeats between games, and a repeated id would
  stop alerting. The timer avoids repeating alerts when monitor_player returns None for an instant.
- With the overlay hidden nothing is read: on return, the items still on the ground alert.
- ItemData may not be filled in at dwMode 5: a failed read or quality 0 is retried on the next tick, up to
  MAX_READ_RETRIES. After that the item is evaluated anyway (only rules without filters match), so the drop does not go
  by silently.
- Runes (drops.DROP_RUNES_FROM): they become ordinary rules, without filters, generated from runes.RUNE_NAMES. No extra
  read: the item already comes from items.read_ground_items, and ItemData is only read while the item is new, as with
  the other rules. main_win passes `tracker.txts` to rune_units, so the rune does not get two markers.

Measured in game (Wirt's Leg dropping from the body, in Tristram): txt 88, quality 2 (normal) already at dwMode 5, then
dwMode 3 and, when picked up, dwMode 0 with the same dwUnitId. With sockets (gray text in game): flags 0x802810, i.e.
FLAG_SOCKETED. To check (public, not measured in this version; DROP_LOG_ALL shows the values): the rest of QUALITY_NAMES
and FLAG_ETHEREAL. Do not trust the public ids without measuring: El is 625, not 610 (runes.py), even though the leg's 88
matched.

"sockets" filter (exact number): ItemData only says whether there are sockets (FLAG_SOCKETED); the count is stat 194
(item_numsockets) in the item's stat list. **Not measured on an item:** read_sockets looks in the +0xE8 list (the one of
monsters and the player, monsters.STAT_ARRAY_OFFSET) and, if not found, in +0x30 (the player's base one), and uses the
raw value (sockets are not fixed point, unlike life and mana). Sockets are only read for the txt with a "sockets" rule
(or with DROP_LOG_ALL, which shows them as sockets=N, and which list they came from, to measure). An item with sockets
without stat 194 read: read again on the next tick, like ItemData at dwMode 5.
"""
import time

from drops import DROP_ALERT_SECONDS, DROP_LOG_ALL, DROP_PLAY_SOUND, DROP_RULES, DROP_RUNES_FROM, DROP_SPEAK
from fabiomh.game.memory import read_struct
from fabiomh.game.monsters import STAT_ARRAY_OFFSET
from fabiomh.game.runes import runes_from
from fabiomh.game.structs import ItemData, StatArray, StatValue
from fabiomh.sound import play_ting, speak

QUALITY_NAMES = {1: "inferior", 2: "normal", 3: "superior", 4: "magic", 5: "set", 6: "rare", 7: "unique", 8: "crafted",
                 9: "tempered"}
FLAG_SOCKETED = 0x800
FLAG_ETHEREAL = 0x400000

RULE_KEYS = {"name", "txt", "enabled", "quality", "ethereal", "socketed", "sockets", "unique_id"}

STAT_NUM_SOCKETS = 194
# Item stat lists in which to look for stat 194, in order (see the top); and the maximum of stats read at once
ITEM_STAT_OFFSETS = (STAT_ARRAY_OFFSET, 0x30)
MAX_ITEM_STATS = 256

GAME_GONE_SECONDS = 5
MAX_READ_RETRIES = 20  # ~3 s with the default TICK_SECONDS


def rune_rules(first_name):
    """Rules for the runes from first_name up, or [] if first_name is None."""
    if first_name is None:
        return []
    return [{"name": f"{name} Rune", "txt": txt} for txt, name in runes_from(first_name)]


def validate_rules(rules):
    """A wrong rule raises ValueError right at startup, like a wrong name in RUNES_TO_SHOW."""
    for rule in rules:
        unknown = set(rule) - RULE_KEYS
        if unknown:
            raise ValueError(f"drops.py: chave desconhecida {sorted(unknown)} em {rule}")
        if "name" not in rule or "txt" not in rule:
            raise ValueError(f"drops.py: regra sem name ou txt: {rule}")
        if not isinstance(rule.get("enabled", True), bool):
            raise ValueError(f"drops.py: enabled tem que ser True ou False: {rule}")
        qualities = rule.get("quality", [])
        if isinstance(qualities, str):
            raise ValueError(f"drops.py: quality tem que ser uma lista: {rule}")
        unknown = set(qualities) - set(QUALITY_NAMES.values())
        if unknown:
            raise ValueError(f"drops.py: qualidade desconhecida {sorted(unknown)} em {rule}")
        sockets = rule.get("sockets", 1)
        if type(sockets) is not int or not 1 <= sockets <= 6:
            raise ValueError(f"drops.py: sockets tem que ser um número de 1 a 6: {rule}")
    return rules


def index_rules(rules):
    """{txt: [enabled rules of that txt]}, in drops.py order (the first one that matches wins). The txt is the most
    restrictive filter: an item with no entry here is out after an O(1) lookup, without reading ItemData, and the other
    filters only run on the rules of its txt (few), however many rules drops.py has."""
    index = {}
    for rule in validate_rules(rules):
        if rule.get("enabled", True):
            index.setdefault(rule["txt"], []).append(rule)
    return index


def needs_sockets(rules, txt):
    """True if some rule of `txt` filters by the number of sockets (only then is it worth reading the stat list)."""
    return any(rule["txt"] == txt and "sockets" in rule for rule in rules)


def read_sockets_at(proc, unit):
    """(sockets, offset of the list where stat 194 was), or (None, None) if not found (see the top)."""
    if not unit.pStatList:
        return None, None
    for offset in ITEM_STAT_OFFSETS:
        try:
            array = read_struct(proc, unit.pStatList + offset, StatArray)
            if not array.pStats or not 0 < array.qwCount <= MAX_ITEM_STATS:
                continue
            stats = read_struct(proc, array.pStats, StatValue * array.qwCount)
        except Exception:
            continue
        for stat in stats:
            if stat.wStat == STAT_NUM_SOCKETS:
                return stat.nValue, offset
    return None, None


def read_sockets(proc, unit, data):
    """Number of sockets of the item: 0 if ItemData says it has no sockets, None if it has but could not be read."""
    if data is not None and not data.ItemFlags & FLAG_SOCKETED:
        return 0
    return read_sockets_at(proc, unit)[0]


def rule_matches(rule, txt, data, sockets=None):
    """data: ItemData, or None if it could not be read (then only a rule without filters matches). sockets:
    read_sockets, or None (then a rule with "sockets" does not match)."""
    if rule["txt"] != txt:
        return False
    if data is None:
        return not set(rule) - {"name", "txt", "enabled"}
    # From the most restrictive filter to the least (the txt, the first one, already came from the index_rules index)
    if "unique_id" in rule and data.dwUniqueOrSetId != rule["unique_id"]:
        return False
    if "quality" in rule and QUALITY_NAMES.get(data.ItemQuality) not in rule["quality"]:
        return False
    if "ethereal" in rule and bool(data.ItemFlags & FLAG_ETHEREAL) != rule["ethereal"]:
        return False
    if "socketed" in rule and bool(data.ItemFlags & FLAG_SOCKETED) != rule["socketed"]:
        return False
    if "sockets" in rule and sockets != rule["sockets"]:
        return False
    return True


def read_item_data(proc, unit):
    if not unit.pUnitData:
        return None
    try:
        return read_struct(proc, unit.pUnitData, ItemData)
    except Exception:
        return None


class DropTracker:
    def __init__(self, rules=DROP_RULES + rune_rules(DROP_RUNES_FROM), log_all=DROP_LOG_ALL,
                 alert_seconds=DROP_ALERT_SECONDS, play_sound=DROP_PLAY_SOUND, speak_names=DROP_SPEAK):
        self.rules_by_txt = index_rules(rules)
        self.txts = set(self.rules_by_txt)
        # txt with some "sockets" rule: only on those is it worth reading the stat list
        self.socket_txts = {txt for txt, txt_rules in self.rules_by_txt.items()
                            if needs_sockets(txt_rules, txt)}
        self.log_all = log_all
        self.alert_seconds = alert_seconds
        self.play_sound = play_sound
        self.speak_names = speak_names
        self.alerts = []        # (when it expires, text)
        self.gone_since = None  # since when monitor_player has been returning None
        self.reset()

    def reset(self):
        self.seed = None
        self.seen = {}     # dwUnitId → name of the rule that matched, or None
        self.retries = {}  # dwUnitId → repeated reads

    def update(self, proc, items, seed):
        """items: [GroundItem]. Returns [(x, y, "drop", name)] of the monitored items on the ground and records the new alerts."""
        self.gone_since = None
        if seed != self.seed:
            self.reset()
            self.seed = seed

        alerts_before = len(self.alerts)
        markers = []
        for item in items:
            unit_id = item.unit.dwUnitId
            if unit_id not in self.seen and not self.inspect(proc, item):
                continue
            name = self.seen[unit_id]
            if name:
                markers.append((item.x, item.y, "drop", name))

        # Only one "ting" per tick, even if several items drop together. With speech, each name is spoken in inspect
        if self.play_sound and not self.speak_names and len(self.alerts) > alerts_before:
            play_ting()
        return markers

    def inspect(self, proc, item):
        """Evaluates a new item. Returns False if it should be read again on the next tick."""
        unit = item.unit
        candidates = self.rules_by_txt.get(unit.dwTxtFileNo)
        if not candidates and not self.log_all:
            # No rule for this txt (most items): decided without reading anything from memory
            self.seen[unit.dwUnitId] = None
            self.retries.pop(unit.dwUnitId, None)
            return True

        data = None
        sockets = None
        wants_sockets = unit.dwTxtFileNo in self.socket_txts

        if candidates or self.log_all:
            data = read_item_data(proc, unit)
            if wants_sockets or self.log_all:
                sockets = read_sockets(proc, unit, data)
            unread = data is None or not data.ItemQuality or (wants_sockets and sockets is None)
            if unread and self.retries.get(unit.dwUnitId, 0) < MAX_READ_RETRIES:
                self.retries[unit.dwUnitId] = self.retries.get(unit.dwUnitId, 0) + 1
                return False

        quality = QUALITY_NAMES.get(data.ItemQuality, "?") if data else "?"
        if self.log_all:
            details = "sem ItemData"
            if data:
                count, offset = read_sockets_at(proc, unit)
                where = f" (stat 194 em +{offset:#x}: {count})" if offset is not None else " (sem o stat 194)"
                details = (f"quality={quality} flags={data.ItemFlags:#x} unique_id={data.dwUniqueOrSetId} "
                           f"sockets={sockets}{where}")
            print(f"==> Item no chão: txt={unit.dwTxtFileNo} id={unit.dwUnitId} {details} pos=({item.x}, {item.y})")

        rule = next((rule for rule in candidates or () if rule_matches(rule, unit.dwTxtFileNo, data, sockets)), None)
        self.seen[unit.dwUnitId] = rule["name"] if rule else None
        self.retries.pop(unit.dwUnitId, None)
        if rule:
            text = f"DROP: {rule['name']} ({quality})"
            print(f"==> {text}")
            self.alerts.append((time.monotonic() + self.alert_seconds, text))
            if self.speak_names:
                speak(rule["name"])
        return True

    def out_of_game(self):
        """Call on the tick in which monitor_player returned None."""
        now = time.monotonic()
        if self.gone_since is None:
            self.gone_since = now
        elif now - self.gone_since >= GAME_GONE_SECONDS:
            self.reset()

    def active_alerts(self):
        """Texts of the banners still valid, from the oldest to the newest."""
        now = time.monotonic()
        self.alerts = [alert for alert in self.alerts if alert[0] > now]
        return [text for _, text in self.alerts]
