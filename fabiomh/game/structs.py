"""ctypes structs of D2R memory (64-bit).

- `_fields_` is assigned after the declarations. Every field has a `# 0xNN` comment with the offset.
- ctypes aligns `c_void_p` to 8 bytes: the padding arrays have to make the pointers land on aligned offsets.
  After changing a struct, check with `Struct.field.offset` (e.g. `UnitAny.pListNext.offset == 0x158`).
- Known UnitAny offsets: pAct 0x20, pPath 0x38, pInventory 0x90, pSkills 0x100, pListNext 0x158,
  playerClass 0x174, isCorpse 0x1A6.
- pListNext is 0x158, measured in all tables: every unit followed through it is in the right type and bucket, and 0x150
  left out everything after the first one in each bucket (82 of 187 items, 10 of 13 players).
- Not verified: UI fields after `inGame` (e.g. `loading`), MonsterData.typeFlags (0x1A, from MapAssist).
"""
import ctypes as ct
from ctypes import Structure, c_bool, c_void_p
from ctypes.wintypes import BYTE, DWORD, WORD
from enum import Enum

class UnitHashTable(Structure):
    pass
class UnitAny(Structure):
    pass
class UI(ct.Structure):
    pass
class Act(Structure):
    pass
class ActNo(Enum):
    act1 = 0
    act2 = 1
    act3 = 2
    act4 = 3
    act5 = 4
class ActMisc(Structure):
    pass
class DynamicPath(Structure):
    pass
class Room1(Structure):
    pass
class Room2(Structure):
    pass
class Level(Structure):
    pass
class MonsterData(Structure):
    pass
class ItemData(Structure):
    pass
class ItemPath(Structure):
    pass
class RosterUnit(Structure):
    pass
class StatArray(Structure):
    pass
class StatValue(Structure):
    pass

UnitHashTable._fields_ = [("table", c_void_p * 128)]
UnitAny._fields_ = [
    ("dwType", DWORD),  # 0x00 unit_type
    ("dwTxtFileNo", DWORD),  # 0x04 txt_file_no
    ("dwUnitId", DWORD),  # 0x08 unit_id
    ("dwMode", DWORD),  # 0x0C mode
    ("pUnitData", c_void_p),  # 0x10 p_unit_data
    ("_dummy1", BYTE * 8),  # 0x18 _dummy (replaces dwAct and _1)
    ("pAct", c_void_p),  # 0x20 p_act
    ("_dummy2", BYTE * 8),  # 0x28 _dummy2
    ("_dummy3", BYTE * 8),  # 0x30 _dummy3
    ("pPath", c_void_p),  # 0x38 p_path
    ("_dummy4", BYTE * 72),  # 0x40 _dummy4 (matches _3)
    ("pStatList", c_void_p),  # 0x88 p_stats_list_ex
    ("pInventory", c_void_p),  # 0x90 p_inventory
    ("_dummy5", BYTE * 16),  # 0x98 _dummy5
    ("_dummy6", BYTE * 8),  # 0xA8 _dummy6
    ("_dummy7", BYTE * 40),  # 0xB0 _dummy7 (includes wX wY)
    ("unkSortStashBy", DWORD),  # 0xD8 unk_sort_stashes_by
    ("_dummy8", BYTE * 36),  # 0xDC _dummy8 (matches _6)
    ("pSkills", c_void_p),  # 0x100 p_skills
    ("_dummy9", BYTE * 72),  # 0x108 _dummy9
    ("_dummy9b", c_void_p),  # 0x150 is not the next one in the list (0 on the units measured)
    ("pListNext", c_void_p),  # 0x158 next unit in the hash table bucket
    ("_dummy10", BYTE * 20),  # 0x160 _dummy10
    ("playerClass", DWORD),  # 0x174 player_class
    ("_dummy11", BYTE * 46),  # 0x178 _dummy11
    ("isCorpse", BYTE),  # 0x1A6 is_corpse
]
UI._fields_ = [
    ("inGame", c_bool),
    ("invMenu", c_bool),
    ("charMenu", c_bool),
    ("skillSelect", c_bool),
    ("skillMenu", c_bool),
    ("_2", BYTE * 3),
    ("npcInteract", c_bool),
    ("quitMenu", c_bool),
    ("_3", BYTE),
    ("npcShop", c_bool),
    ("_4", BYTE * 2),
    ("questsMenu", c_bool),
    ("_5", BYTE * 3),
    ("isNotPlayerAlone", c_bool),
    ("waypointMenu", c_bool),
    ("_6", BYTE),
    ("partyMenu", c_bool),
    ("_7", BYTE * 2),
    ("stash", c_bool),
    ("_8", BYTE * 5),
    ("mercMenu", c_bool),
    ("_9", BYTE * 0x101),
    ("bAct", BYTE),
    ("_10", BYTE * 0x37),
    ("pUnkUI", c_void_p),
    ("_11", BYTE * 0xC),
    ("loading", BYTE),
]
Act._fields_ = [
    ("_dummy", BYTE * 112),  # 0x00..0x6F
    ("pActMisc", c_void_p),  # 0x70
]
ActMisc._fields_ = [
    ("_dummy", BYTE * 2096),  # 0x000..0x82F
    ("game_difficulty", DWORD),  # 0x830
    ("_dummy2", BYTE * 12),  # 0x834
    ("dw_init_seed_hash", ct.c_uint64),  # 0x840
    ("_dummy3", BYTE * 24),  # 0x848
    ("dw_end_seed_hash", DWORD),  # 0x860
    ("_dummy4", BYTE * 24),  # 0x864
]
Room1._fields_ = [
    ("pRoomsNear", c_void_p),  # 0x00
    ("_1", c_void_p),  # 0x08 some pointer
    ("_2", DWORD * 2),  # 0x10
    ("pRoom2", c_void_p),  # 0x18
    ("_3", DWORD * 5),  # 0x20
    ("Coll", c_void_p),  # 0x38
    ("dwRoomsNear", DWORD),  # 0x40
    ("_4", DWORD),  # 0x44
    ("pAct", c_void_p),  # 0x48
    ("_5", DWORD * 0x0C),  # 0x50
    ("dwXStart", DWORD),  # 0x80
    ("dwYStart", DWORD),  # 0x84
    ("dwXSize", DWORD),  # 0x88
    ("dwYSize", DWORD),  # 0x8C
    ("_6", DWORD * 6),  # 0x90
    ("pUnitFirst", c_void_p),  # 0xA8
    ("pRoomNext", c_void_p),  # 0xB0
]
Room2._fields_ = [
    ("_1", DWORD * 4),  # 0x00
    ("pRoom2Near", c_void_p),  # 0x10
    ("_2", DWORD * 7),  # 0x18
    ("_3", c_void_p),  # 0x38
    ("_4", c_void_p),  # 0x40 some pointer
    ("pRoom2Next", c_void_p),  # 0x48
    ("_5", DWORD * 2),  # 0x50
    ("pRoom1", c_void_p),  # 0x58
    ("dwPosX", DWORD),  # 0x60
    ("dwPosY", DWORD),  # 0x64
    ("dwSizeX", DWORD),  # 0x68
    ("dwSizeY", DWORD),  # 0x6C
    ("_6", DWORD * 6),  # 0x70
    ("_7", c_void_p),  # 0x88
    ("pLevel", c_void_p),  # 0x90
    ("pPreset", c_void_p),  # 0x98
]
Level._fields_ = [
    ("_1", DWORD * 4),  # 0x00
    ("pRoom2First", c_void_p),  # 0x10
    ("_2", DWORD * 4),  # 0x18
    ("dwPosX", DWORD),  # 0x28
    ("dwPosY", DWORD),  # 0x2C
    ("dwSizeX", DWORD),  # 0x30
    ("dwSizeY", DWORD),  # 0x34
    ("_3", DWORD * 0x60),  # 0x38
    ("pNextLevel", c_void_p),  # 0x1B8
    ("_4", c_void_p),  # 0x1C0
    ("pActMisc", c_void_p),  # 0x1C8
    ("_5", DWORD * 0xA),  # 0x1D0
    ("dwLevelNo", DWORD),  # 0x1F8
    ("_6", DWORD * 3),  # 0x1FC
    ("RoomCenterWrapX", DWORD * 9),  # 0x208
    ("RoomCenterWrapY", DWORD * 9),  # 0x22C
    ("dwRoomEntries", DWORD),  # 250
]
DynamicPath._fields_ = [
    ("xOffset", WORD),  # 0x00
    ("xPos", WORD),  # 0x02
    ("yOffset", WORD),  # 0x04
    ("yPos", WORD),  # 0x06
    ("_1", DWORD * 6),  # 0x08
    ("pRoom1", c_void_p),  # 0x20
    ("pRoom1Unk", c_void_p),  # 0x28
    ("_2", DWORD * 4),  # 0x30
    ("pUnit", c_void_p),  # 0x40
    ("_3", 10 * DWORD),  # 0x48
    ("pUnitTarget", c_void_p),  # 0x70
    ("dwTargetType", DWORD),  # 0x78
    ("dwTargetId", DWORD),  # 0x7C
    ("_3", BYTE * 2),  # 0x80
    ("bDirection", BYTE),  # 0x82 not sure about this
    ("_4", BYTE),  # 0x83
    ("_5", DWORD * 17),  # 0x84
    ("xTarget", WORD),  # 0xC8
    ("yTarget", WORD),  # 0xCA
]
MonsterData._fields_ = [
    ("_1", BYTE * 0x1A),  # 0x00
    ("typeFlags", BYTE),  # 0x1A 1=other 2=super unique 4=champion 8=unique 16=minion (to be verified)
]
# Stat list of a unit (UnitAny.pStatList), read at monsters.STAT_ARRAY_OFFSET. Measured in game (diag_stats.py)
StatArray._fields_ = [
    ("pStats", c_void_p),  # 0x00 first StatValue
    ("qwCount", ct.c_uint64),  # 0x08
]
StatValue._fields_ = [
    ("wLayer", WORD),  # 0x00
    ("wStat", WORD),  # 0x02 ItemStatCost id
    ("nValue", ct.c_int32),  # 0x04
]
ItemData._fields_ = [
    ("ItemQuality", DWORD),  # 0x0
    ("_1", DWORD * 2),  # 0x4
    ("dwOwnerId", DWORD),  # 0xC
    ("_2", DWORD * 2),  # 0x10
    ("ItemFlags", DWORD),  # 0x18
    ("_3", DWORD * 6),  # 0x1C
    ("dwUniqueOrSetId", DWORD),  # 0x34
    ("_4", DWORD * 2),  # 0x38
    ("_5", WORD),  # 0x40
    ("RarePrefix", WORD),  # 0x42
    ("RareSuffix", WORD),  # 0x44
    ("AutoAffix", WORD),  # 0x46
    ("MagicPrefix", WORD * 3),  # 0x48
    ("MagicSuffix", WORD * 3),  # 0x4E
    ("bBodyLoc", BYTE),  # 0x54
    ("bInvPage", BYTE),  # 0x55
    ("_6", WORD * 4),  # 0x56
    ("wSkinId", WORD),  # 0x5E
]
ItemPath._fields_ = [
    ("_1", DWORD * 4),  # 0x00
    ("xPos", WORD),  # 0x10
    ("_2", WORD),  # 0x12
    ("yPos", WORD),  # 0x14
]
# List of players in the game (the party panel one), at memory.ROSTER_OFFSET. Measured in game (3.3.93847)
RosterUnit._fields_ = [
    ("szName", ct.c_char * 16),  # 0x00
    ("_1", BYTE * 0x38),  # 0x10
    ("dwUnitId", DWORD),  # 0x48
    ("dwPartyLife", DWORD),  # 0x4C life in %
    ("_2", DWORD),  # 0x50
    ("dwClassId", DWORD),  # 0x54
    ("wLevel", WORD),  # 0x58
    ("wPartyId", WORD),  # 0x5A 0xFFFF = not in a party
    ("dwLevelId", DWORD),  # 0x5C area; 0 outside the party
    ("dwPosX", DWORD),  # 0x60 0 on the local player and outside the party
    ("dwPosY", DWORD),  # 0x64
    ("_3", BYTE * 0xE0),  # 0x68
    ("pNext", c_void_p),  # 0x148
]
