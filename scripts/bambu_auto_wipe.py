#!/usr/bin/env python3
r"""
Bambu Auto-Wipe: 按挤出长度自动清洁喷嘴的 Bambu Studio 后处理脚本
Post-processing script for Bambu Studio that wipes nozzle by accumulated extrusion length.

支持机型 / Supported: H2D / A1 / A1 mini / P1P / P1S / X1 / X1C
支持平台 / Platforms: Windows / macOS / Linux

用法 / Usage (Bambu Studio -> Printer Settings -> General -> Post-processing scripts):
  Windows:  C:\Python311\python.exe "C:\path\to\bambu_auto_wipe.py"
  macOS:    /usr/bin/python3 "/path/to/bambu_auto_wipe.py"
  Linux:    /usr/bin/python3 "/path/to/bambu_auto_wipe.py"

配置 / Config: 同目录下的 config.json / config.json next to this script (optional).
"""

import sys
import re
import os
import json
import time
import shutil

# ===== 默认配置 / Default config (override via config.json) =====
DEFAULTS = {
    "wipe_every_mm": 200.0,       # 每挤出多少 mm 耗材擦一次 / Extrusion length between wipes (mm)
    "only_infill": True,           # 只在填充段触发，零表面影响 / Only trigger during infill
    "retract_mm": 0.8,             # 擦前回抽量（mm）/ Retract before wipe (mm)
    "restore_mm": 0.8,             # 擦后补压量（mm）/ Restore pressure after wipe (mm)
    "retract_speed": 300,          # 回抽速度 (mm/min) / Retract speed (mm/min)
    "force_printer_model": None,   # None=自动检测；也可强制指定 / None=auto-detect; or force "H2D"/"A1"/"P1S"/"X1C"
}

# ===== 各机型清洁喷嘴指令表 / Printer-specific wipe G-code =====
# H2D 用固件内置 G150.1/G150.3；其他机型用手动坐标扫擦
# H2D uses firmware-native G150.1/G150.3; others use manual coordinate sweep
PRINTER_WIPE_GCODE = {
    "H2D": {
        "pre":  [],
        "move": ["G150.1 ; move to purge wiper / 移到清洁刷位置"],
        "wipe": ["G150.3 ; perform wipe cycle / 执行清洁循环"],
        "post": [],
    },
    "A1": {
        "pre":  ["G90 ; absolute mode / 绝对坐标模式"],
        "move": ["G1 X55 Y262.5 F15000 ; move to A1 purge wiper / 移到 A1 清洁刷位置"],
        "wipe": [
            "G91 ; relative mode / 相对坐标模式",
            "G1 X-35 F6000 ; wipe left / 左扫",
            "G1 X45 F6000 ; wipe right / 右扫",
            "G90 ; back to absolute / 返回绝对坐标",
        ],
        "post": [],
    },
    "P1P": {
        "pre":  ["G90"],
        "move": ["G1 X10 Y245 F15000 ; P1P purge wiper / P1P 清洁刷位置"],
        "wipe": [
            "G91",
            "G1 X-30 F6000",
            "G1 X40 F6000",
            "G90",
        ],
        "post": [],
    },
    "X1C": {
        "pre":  ["G90"],
        "move": ["G1 X10 Y245 F15000 ; X1C purge wiper / X1C 清洁刷位置"],
        "wipe": [
            "G91",
            "G1 X-30 F6000",
            "G1 X40 F6000",
            "G90",
        ],
        "post": [],
    },
}
# 别名（自动检测时归一化）/ Aliases (normalized during auto-detect)
MODEL_ALIASES = {
    "H2D": "H2D", "H2DR": "H2D",
    "A1": "A1", "A1MINI": "A1", "A1 MINI": "A1",
    "P1P": "P1P", "P1S": "P1P",
    "X1": "X1C", "X1C": "X1C", "X1CARBON": "X1C",
}


def load_config(script_dir):
    cfg = dict(DEFAULTS)
    cfg_path = os.path.join(script_dir, "config.json")
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                user = json.load(f)
            cfg.update({k: v for k, v in user.items() if k in DEFAULTS})
        except Exception as e:
            print(f"[bambu_auto_wipe] WARNING: could not parse config.json: {e}",
                  file=sys.stderr)
    return cfg


def detect_printer_model(lines, force=None):
    if force:
        return MODEL_ALIASES.get(force.upper(), force.upper())
    # Bambu gcode 头部注释里有打印机型号 / Printer model in Bambu gcode header
    for line in lines[:200]:
        m = re.search(r';\s*(?:printer_model|machine|printer)\s*:\s*(\S+)',
                      line, re.IGNORECASE)
        if m:
            raw = m.group(1).strip().upper()
            if raw in MODEL_ALIASES:
                return MODEL_ALIASES[raw]
    # fallback: 看是否有 G150 指令（只有 H2D 固件用）/ fallback: G150 = H2D firmware
    for line in lines[:500]:
        if "G150" in line:
            return "H2D"
    return "A1"  # 默认 A1 坐标 / default A1 coordinates


def parse_e(line):
    m = re.search(r' E(-?[\d.]+)', line, re.IGNORECASE)
    return float(m.group(1)) if m else None


def is_infill_line(stripped):
    return stripped.startswith(";") and "infill" in stripped.lower()


def is_wall_or_outer(stripped):
    if not stripped.startswith(";"):
        return False
    s = stripped.lower()
    return any(k in s for k in ["wall", "top", "support", "skirt", "brim"])


def main():
    if len(sys.argv) < 2:
        print("Usage: bambu_auto_wipe.py <gcode-file>", file=sys.stderr)
        sys.exit(1)

    orig_path = sys.argv[1]
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cfg = load_config(script_dir)

    # 复制到临时目录处理，绕过 Bambu Studio 独占锁
    # Copy to temp dir to bypass Bambu Studio exclusive file lock
    tmp_dir = os.path.join(
        os.environ.get("TEMP") or os.environ.get("TMPDIR") or "/tmp",
        "bambu_auto_wipe_tmp",
    )
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_path = os.path.join(tmp_dir, "input.gcode")
    shutil.copy2(orig_path, tmp_path)

    with open(tmp_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    model = detect_printer_model(lines, cfg["force_printer_model"])
    wipe_seq = PRINTER_WIPE_GCODE.get(model, PRINTER_WIPE_GCODE["A1"])

    out = []
    last_e = 0.0
    rel_mode = False
    since_wipe = 0.0
    wiped = 0
    pending = False
    in_infill = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith(";") and not stripped.startswith("; ---"):
            if is_infill_line(stripped):
                in_infill = True
            elif is_wall_or_outer(stripped):
                in_infill = False

        if re.search(r"M83\b", stripped):
            rel_mode = True
        elif re.search(r"M82\b", stripped):
            rel_mode = False

        g92 = re.match(r"\s*G92\s+E(-?[\d.]+)", stripped, re.IGNORECASE)
        if g92:
            last_e = float(g92.group(1))

        e = parse_e(line)
        is_move = re.match(r"^\s*G[01]\b", stripped, re.IGNORECASE)
        if e is not None and is_move:
            if rel_mode:
                delta = e
                last_e = last_e + e
            else:
                delta = e - last_e
                last_e = e
            if delta > 0:
                since_wipe += delta

            if since_wipe >= cfg["wipe_every_mm"]:
                pending = True

            # 只在填充段触发（零表面影响）/ Only trigger during infill
            if pending and (not cfg["only_infill"] or in_infill):
                out.append(
                    f"; --- auto wipe ({since_wipe:.1f} mm since last, {model}) ---\n"
                )
                out.append("G92 E0\n")
                out.append(
                    f"G1 E-{cfg['retract_mm']} F{cfg['retract_speed']} ; retract / 回抽\n"
                )
                for g in wipe_seq["pre"]:
                    out.append(g + "\n")
                for g in wipe_seq["move"]:
                    out.append(g + "\n")
                for g in wipe_seq["wipe"]:
                    out.append(g + "\n")
                for g in wipe_seq["post"]:
                    out.append(g + "\n")
                out.append(
                    f"G1 E{cfg['restore_mm']} F{cfg['retract_speed']} ; restore pressure / 恢复挤出压力\n"
                )
                out.append("G92 E0\n")
                out.append("; --------------------------------------------------------\n")
                since_wipe = 0.0
                pending = False
                wiped += 1

        out.append(line)

    with open(tmp_path, "w", encoding="utf-8") as f:
        f.writelines(out)

    # 写回原文件（等 Bambu 释放锁）/ Write back to original (wait for Bambu lock release)
    time.sleep(1.0)
    try:
        shutil.copy2(tmp_path, orig_path)
    except PermissionError:
        # fallback: 存到用户文档目录 / fallback: save to Documents
        home = os.path.expanduser("~")
        fallback = os.path.join(home, "Documents", "last_patched.gcode")
        try:
            shutil.copy2(tmp_path, fallback)
            print(f"[bambu_auto_wipe] WARNING: locked by Bambu, saved to {fallback}",
                  file=sys.stderr)
        except Exception:
            pass

    print(
        f"[bambu_auto_wipe] model={model} injected {wiped} wipes "
        f"(every {cfg['wipe_every_mm']:.0f} mm E, infill_only={cfg['only_infill']})"
    )


if __name__ == "__main__":
    main()
