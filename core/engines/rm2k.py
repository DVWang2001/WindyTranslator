"""
RPG Maker 2000/2003 (RM2k/RM2k3) supplemental support.

Extracts and re-imports map names, switch names, variable names, and
common event names from the LCF binary files RPG_RT.lmt / RPG_RT.ldb.
These labels are NOT exported by RPGRewriter, so this module fills the gap.

Export writes  StringScripts/RM2K_Names.txt  (UTF-8).
Import reads that file and patches the binary files in-place (with .bak backup).

Confirmed section keys (from binary inspection of a real RM2k/2003 game):
  LMT : flat node array directly after magic  (field 0x01 = name)
  LDB 0x17 = Switches   (field 0x01 = name)
  LDB 0x18 = Variables  (field 0x01 = name)
  LDB 0x19 = CommonEvents (field 0x01 = name)
"""

import logging
import os
import shutil
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

STRING_SCRIPTS_DIRNAME = "StringScripts"
RM2K_NAMES_FILENAME = "RM2K_Names.txt"

# LDB section keys (confirmed by binary inspection)
LDB_SWITCHES_KEY      = 0x17
LDB_VARIABLES_KEY     = 0x18
LDB_COMMON_EVENTS_KEY = 0x19

# Field key for "name" inside every entry
FIELD_NAME = 0x01

# StringScripts section markers
SEC_MAP_NAMES    = "RM2K_MapNames"
SEC_SWITCHES     = "RM2K_Switches"
SEC_VARIABLES    = "RM2K_Variables"
SEC_COMMON_EVENTS = "RM2K_CommonEvents"

# Encoding-code → Python codec
_CODE_TO_CODEC: Dict[str, str] = {
    "932":   "cp932",
    "936":   "gbk",
    "950":   "big5",
    "1252":  "cp1252",
    "1251":  "cp1251",
    "1250":  "cp1250",
    "65001": "utf-8",
    "0":     "cp932",
}


def _codec(code: str) -> str:
    return _CODE_TO_CODEC.get(str(code), "cp932")


# ── BER codec ────────────────────────────────────────────────────────────────

def _read_ber(data: bytes, pos: int) -> Tuple[int, int]:
    value = 0
    while pos < len(data):
        b = data[pos]; pos += 1
        value = (value << 7) | (b & 0x7F)
        if not (b & 0x80):
            break
    return value, pos


def _write_ber(n: int) -> bytes:
    if n == 0:
        return b"\x00"
    parts: List[int] = []
    while n:
        parts.append(n & 0x7F)
        n >>= 7
    parts.reverse()
    for i in range(len(parts) - 1):
        parts[i] |= 0x80
    return bytes(parts)


# ── Generic flat-array parser/serialiser ─────────────────────────────────────

def _parse_array(data: bytes, pos: int = 0) -> List[Tuple[int, Dict[int, bytes]]]:
    """Parse BER-count + N entries, each: [BER id][fields...][0x00]."""
    count, pos = _read_ber(data, pos)
    entries: List[Tuple[int, Dict[int, bytes]]] = []
    for _ in range(count):
        if pos >= len(data):
            break
        eid, pos = _read_ber(data, pos)
        fields: Dict[int, bytes] = {}
        while pos < len(data):
            fk, pos = _read_ber(data, pos)
            if fk == 0:
                break
            fs, pos = _read_ber(data, pos)
            fields[fk] = data[pos: pos + fs]
            pos += fs
        entries.append((eid, fields))
    return entries


def _serialise_array(entries: List[Tuple[int, Dict[int, bytes]]]) -> bytes:
    """Serialise entries list back to flat-array bytes."""
    out = bytearray(_write_ber(len(entries)))
    for eid, fields in entries:
        out += _write_ber(eid)
        for fk in sorted(fields.keys()):
            fdata = fields[fk]
            out += _write_ber(fk)
            out += _write_ber(len(fdata))
            out += fdata
        out += b"\x00"
    return bytes(out)


# ── LDB helpers (sections wrapper) ───────────────────────────────────────────

def _read_ldb(data: bytes) -> Tuple[bytes, List[Tuple[int, bytes]]]:
    """Return (magic_bytes, [(key, section_data), ...])."""
    ml, pos = _read_ber(data, 0)
    magic = data[pos: pos + ml]
    pos += ml
    sections: List[Tuple[int, bytes]] = []
    while pos < len(data):
        key, pos = _read_ber(data, pos)
        if key == 0:
            break
        sz, pos = _read_ber(data, pos)
        sections.append((key, data[pos: pos + sz]))
        pos += sz
    return magic, sections


def _write_ldb(magic: bytes, sections: List[Tuple[int, bytes]]) -> bytes:
    out = bytearray(_write_ber(len(magic)))
    out += magic
    for key, sec in sections:
        out += _write_ber(key)
        out += _write_ber(len(sec))
        out += sec
    return bytes(out)


# ── LMT helpers (flat array directly after magic) ────────────────────────────

def _read_lmt(data: bytes) -> Tuple[bytes, List[Tuple[int, Dict[int, bytes]]]]:
    """Return (magic_bytes, node_entries)."""
    ml, pos = _read_ber(data, 0)
    magic = data[pos: pos + ml]
    pos += ml
    entries = _parse_array(data, pos)
    return magic, entries


def _write_lmt(magic: bytes, entries: List[Tuple[int, Dict[int, bytes]]]) -> bytes:
    out = bytearray(_write_ber(len(magic)))
    out += magic
    out += _serialise_array(entries)
    return bytes(out)


# ── StringScripts format ─────────────────────────────────────────────────────

_SECTION_ORDER = [
    (SEC_MAP_NAMES,     "地圖名稱"),
    (SEC_SWITCHES,      "開關名稱"),
    (SEC_VARIABLES,     "變數名稱"),
    (SEC_COMMON_EVENTS, "公共事件名稱"),
]

_ENTRY_SEP = "*" * 5
_ID_SEP    = "-" * 5


def _write_names_file(names: Dict[str, Dict[int, str]]) -> str:
    lines: List[str] = []
    for sec_key, sec_label in _SECTION_ORDER:
        lines.append(f"{_ENTRY_SEP}{sec_key}{_ENTRY_SEP}")
        section = names.get(sec_key, {})
        for eid in sorted(section.keys()):
            lines.append(f"{_ID_SEP}{eid}{_ID_SEP}")
            lines.append(section[eid])
        lines.append("")
    return "\n".join(lines)


def _parse_names_file(content: str) -> Dict[str, Dict[int, str]]:
    result: Dict[str, Dict[int, str]] = {}
    current_sec: Optional[str] = None
    current_id:  Optional[int]  = None
    pending_lines: List[str] = []

    def _flush():
        if current_sec is not None and current_id is not None:
            result.setdefault(current_sec, {})[current_id] = "\n".join(pending_lines).rstrip("\n")

    for raw in content.splitlines():
        # Section header: *****RM2K_MapNames*****
        if raw.startswith(_ENTRY_SEP) and raw.endswith(_ENTRY_SEP) and len(raw) > 10:
            _flush()
            pending_lines.clear()
            current_id = None
            current_sec = raw.strip("*").strip()
            continue

        # ID marker: -----1-----
        if raw.startswith(_ID_SEP) and raw.endswith(_ID_SEP) and len(raw) > 10:
            _flush()
            pending_lines.clear()
            try:
                current_id = int(raw.strip("-").strip())
            except ValueError:
                current_id = None
            continue

        # Content line (only collect if inside a valid section+id)
        if current_sec is not None and current_id is not None:
            pending_lines.append(raw)

    _flush()
    return result


# ── Extract helpers ───────────────────────────────────────────────────────────

def _extract_names(entries: List[Tuple[int, Dict[int, bytes]]], enc: str,
                   skip_zero: bool = False) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for eid, fields in entries:
        if skip_zero and eid == 0:
            continue
        raw = fields.get(FIELD_NAME, b"")
        if raw:
            out[eid] = raw.decode(enc, errors="replace")
    return out


# ── Public API ────────────────────────────────────────────────────────────────

def export_names(game_path: str, encoding_code: str, message_queue=None) -> bool:
    """
    Export map names, switch names, variable names, and common event names
    to StringScripts/RM2K_Names.txt.
    Must be called AFTER RPGRewriter export (StringScripts dir already exists).
    """
    def _log(level: str, msg: str):
        log.info(msg)
        if message_queue:
            message_queue.put(("log", (level, msg)))

    enc = _codec(encoding_code)
    lmt_path = os.path.join(game_path, "RPG_RT.lmt")
    ldb_path = os.path.join(game_path, "RPG_RT.ldb")
    ss_dir   = os.path.join(game_path, STRING_SCRIPTS_DIRNAME)
    os.makedirs(ss_dir, exist_ok=True)

    names: Dict[str, Dict[int, str]] = {
        SEC_MAP_NAMES:     {},
        SEC_SWITCHES:      {},
        SEC_VARIABLES:     {},
        SEC_COMMON_EVENTS: {},
    }

    # ── LMT ──
    if os.path.isfile(lmt_path):
        try:
            _, lmt_entries = _read_lmt(open(lmt_path, "rb").read())
            names[SEC_MAP_NAMES] = _extract_names(lmt_entries, enc, skip_zero=True)
            _log("normal", f"  [RM2K] 地圖名稱: {len(names[SEC_MAP_NAMES])} 個")
        except Exception as e:
            _log("warning", f"  [RM2K] 解析 LMT 失敗: {e}")

    # ── LDB ──
    if os.path.isfile(ldb_path):
        try:
            _, ldb_secs = _read_ldb(open(ldb_path, "rb").read())
            for key, sec_data in ldb_secs:
                if key == LDB_SWITCHES_KEY:
                    names[SEC_SWITCHES] = _extract_names(_parse_array(sec_data), enc)
                    _log("normal", f"  [RM2K] 開關名稱: {len(names[SEC_SWITCHES])} 個")
                elif key == LDB_VARIABLES_KEY:
                    names[SEC_VARIABLES] = _extract_names(_parse_array(sec_data), enc)
                    _log("normal", f"  [RM2K] 變數名稱: {len(names[SEC_VARIABLES])} 個")
                elif key == LDB_COMMON_EVENTS_KEY:
                    names[SEC_COMMON_EVENTS] = _extract_names(_parse_array(sec_data), enc)
                    _log("normal", f"  [RM2K] 公共事件名稱: {len(names[SEC_COMMON_EVENTS])} 個")
        except Exception as e:
            _log("warning", f"  [RM2K] 解析 LDB 失敗: {e}")

    # ── Write file ──
    out_path = os.path.join(ss_dir, RM2K_NAMES_FILENAME)
    try:
        content = _write_names_file(names)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        total = sum(len(v) for v in names.values())
        _log("success", f"  [RM2K] 已寫入 {RM2K_NAMES_FILENAME}，共 {total} 個名稱")
        return True
    except Exception as e:
        _log("error", f"  [RM2K] 寫入名稱文件失敗: {e}")
        return False


def import_names(game_path: str, encoding_code: str, message_queue=None) -> bool:
    """
    Import translated names from StringScripts/RM2K_Names.txt back into
    RPG_RT.lmt and RPG_RT.ldb.  Original files are backed up as *.bak.
    """
    def _log(level: str, msg: str):
        log.info(msg)
        if message_queue:
            message_queue.put(("log", (level, msg)))

    enc      = _codec(encoding_code)
    lmt_path = os.path.join(game_path, "RPG_RT.lmt")
    ldb_path = os.path.join(game_path, "RPG_RT.ldb")
    names_path = os.path.join(game_path, STRING_SCRIPTS_DIRNAME, RM2K_NAMES_FILENAME)

    if not os.path.isfile(names_path):
        _log("normal", f"  [RM2K] 未找到 {RM2K_NAMES_FILENAME}，跳過名稱導入")
        return True

    try:
        translations = _parse_names_file(
            open(names_path, "r", encoding="utf-8").read()
        )
    except Exception as e:
        _log("error", f"  [RM2K] 讀取名稱文件失敗: {e}")
        return False

    map_tr  = translations.get(SEC_MAP_NAMES,     {})
    sw_tr   = translations.get(SEC_SWITCHES,      {})
    var_tr  = translations.get(SEC_VARIABLES,     {})
    ce_tr   = translations.get(SEC_COMMON_EVENTS, {})

    ok = True

    # ── Patch LMT ──
    if map_tr and os.path.isfile(lmt_path):
        try:
            ok = ok and _patch_lmt(lmt_path, map_tr, enc, _log)
        except Exception as e:
            _log("error", f"  [RM2K] 更新 LMT 失敗: {e}")
            ok = False

    # ── Patch LDB ──
    if (sw_tr or var_tr or ce_tr) and os.path.isfile(ldb_path):
        try:
            ok = ok and _patch_ldb(ldb_path, sw_tr, var_tr, ce_tr, enc, _log)
        except Exception as e:
            _log("error", f"  [RM2K] 更新 LDB 失敗: {e}")
            ok = False

    total = len(map_tr) + len(sw_tr) + len(var_tr) + len(ce_tr)
    if ok:
        _log("success", f"  [RM2K] 名稱導入完成，共處理 {total} 個項目")
    return ok


# ── Internal patch helpers ────────────────────────────────────────────────────

def _encode_name(name: str, enc: str, label: str, _log) -> Optional[bytes]:
    """Encode a translated name; return None to keep original on failure."""
    try:
        return name.encode(enc, errors="strict")
    except (UnicodeEncodeError, LookupError):
        _log("warning", f"  [RM2K] 無法將 {label!r} 編碼為 {enc}，保留原文")
        return None


def _patch_lmt(lmt_path: str, translations: Dict[int, str],
               enc: str, _log) -> bool:
    magic, entries = _read_lmt(open(lmt_path, "rb").read())
    new_entries = []
    count = 0
    for eid, fields in entries:
        if eid in translations:
            nb = _encode_name(translations[eid], enc, f"map {eid}", _log)
            if nb is not None:
                fields = dict(fields)
                fields[FIELD_NAME] = nb
                count += 1
        new_entries.append((eid, fields))

    if count == 0:
        _log("normal", "  [RM2K] LMT: 無符合的地圖名稱需要更新")
        return True

    _backup(lmt_path, _log)
    with open(lmt_path, "wb") as f:
        f.write(_write_lmt(magic, new_entries))
    _log("success", f"  [RM2K] RPG_RT.lmt: 已更新 {count} 個地圖名稱")
    return True


def _patch_ldb(ldb_path: str,
               sw_tr: Dict[int, str], var_tr: Dict[int, str],
               ce_tr: Dict[int, str], enc: str, _log) -> bool:
    magic, sections = _read_ldb(open(ldb_path, "rb").read())
    new_sections: List[Tuple[int, bytes]] = []
    total = 0

    for key, sec_data in sections:
        if key == LDB_SWITCHES_KEY and sw_tr:
            sec_data, n = _patch_section_names(sec_data, sw_tr, enc, f"開關", _log)
            total += n
        elif key == LDB_VARIABLES_KEY and var_tr:
            sec_data, n = _patch_section_names(sec_data, var_tr, enc, f"變數", _log)
            total += n
        elif key == LDB_COMMON_EVENTS_KEY and ce_tr:
            sec_data, n = _patch_section_names(sec_data, ce_tr, enc, f"公共事件", _log)
            total += n
        new_sections.append((key, sec_data))

    if total == 0:
        _log("normal", "  [RM2K] LDB: 無符合項目需要更新")
        return True

    _backup(ldb_path, _log)
    with open(ldb_path, "wb") as f:
        f.write(_write_ldb(magic, new_sections))
    _log("success", f"  [RM2K] RPG_RT.ldb: 已更新 {total} 個名稱")
    return True


def _patch_section_names(sec_data: bytes, translations: Dict[int, str],
                          enc: str, label: str, _log) -> Tuple[bytes, int]:
    entries = _parse_array(sec_data)
    new_entries = []
    count = 0
    for eid, fields in entries:
        if eid in translations:
            nb = _encode_name(translations[eid], enc, f"{label} {eid}", _log)
            if nb is not None:
                fields = dict(fields)
                fields[FIELD_NAME] = nb
                count += 1
        new_entries.append((eid, fields))
    if count:
        _log("normal", f"  [RM2K] {label}: 更新 {count} 個")
    return _serialise_array(new_entries), count


def _backup(path: str, _log) -> None:
    bak = path + ".bak"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
        _log("normal", f"  [RM2K] 已備份 {os.path.basename(path)} → .bak")
