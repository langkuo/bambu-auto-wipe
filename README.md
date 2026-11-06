# bambu-auto-wipe

按挤出长度自动清洁喷嘴的 Bambu Studio 后处理脚本。只在填充（infill）段触发，零表面影响。

Post-processing script for Bambu Studio that automatically wipes the nozzle by accumulated extrusion length. Triggers only during infill moves — zero visible impact on surface quality.

---

## 支持机型 / Supported Printers

| 机型 / Printer | 自动检测 / Auto-detect | 手动指定 / Manual |
|---|---|---|
| H2D | ✅ | `"H2D"` |
| A1 / A1 mini | ✅ | `"A1"` |
| P1P / P1S | ✅ | `"P1P"` |
| X1 / X1C | ✅ | `"X1C"` |

---

## 为什么需要这个脚本 / Why This Exists

Bambu Studio 没有"按累计挤出量触发清洁喷嘴"的内置功能。默认的清洁刷（purge wiper）只在换料或打印开头用一次，打大件中间喷嘴脏了、拉丝了，只能手动擦。

Bambu Studio has no built-in "wipe by accumulated extrusion" feature. The stock purge wiper only runs at filament swap or print start — on long prints, the nozzle gets dirty and stringy mid-print with no automated cleanup.

这个脚本会扫描完整 G-code，按你设定的挤出长度（默认 200mm）自动在 **填充段中间**插入清洁动作，不打断外观面。

This script scans the full sliced G-code, counts real extrusion (honoring `G92 E0` resets and M82/M83 modes), and inserts a wipe cycle **mid-infill** exactly when your configured extrusion threshold is hit — never on outer walls or top surfaces.

---

## 安装 / Installation

### 1. 下载脚本 / Download

```bash
git clone https://github.com/langkuo/bambu-auto-wipe.git
# 或 / Or: 直接下载 scripts/bambu_auto_wipe.py 和 config.json 到同一文件夹
```

### 2. Bambu Studio 配置 / Configure Bambu Studio

**打印机设置 → 通用 → 后处理脚本 / Printer Settings → General → Post-processing scripts**

填入完整路径（必须用解释器 + 脚本，不能只写 `python`）：

Use the full interpreter path + script path (bare `python` will not work):

```
# Windows
C:\Python311\python.exe "C:\path\to\bambu-auto-wipe\scripts\bambu_auto_wipe.py"

# macOS
/usr/bin/python3 "/path/to/bambu-auto-wipe/scripts/bambu_auto_wipe.py"

# Linux
/usr/bin/python3 "/path/to/bambu-auto-wipe/scripts/bambu_auto_wipe.py"
```

### 3. 调参数（可选）/ Tune Parameters (Optional)

编辑同目录下的 `config.json` / Edit `config.json` next to the script:

```json
{
  "wipe_every_mm": 200.0,
  "only_infill": true,
  "retract_mm": 0.8,
  "restore_mm": 0.8,
  "retract_speed": 300,
  "force_printer_model": null
}
```

| 参数 / Key | 含义 / Meaning |
|---|---|
| `wipe_every_mm` | 每挤出多少 mm 耗材擦一次 / Extrusion length between wipes (mm) |
| `only_infill` | 只在填充段触发，零表面影响 / Only trigger during infill (no surface impact) |
| `retract_mm` | 擦前回抽量（mm）/ Retract before wipe (mm) |
| `restore_mm` | 擦后补压量（mm）/ Restore pressure after wipe (mm) |
| `retract_speed` | 回抽速度（mm/min）/ Retract speed (mm/min) |
| `force_printer_model` | 强制指定机型（默认自动检测）/ Force printer model (default: auto-detect) |

### 参数调优表 / Recommended Values by Filament

| 耗材 / Filament | `wipe_every_mm` | 说明 / Notes |
|---|---|---|
| PLA | 300.0 | 几乎不拉丝，省时间 / Minimal stringing, save time |
| PETG | 200.0 | 平衡防拉丝 vs 时间损失 / Balanced anti-stringing vs time cost |
| ABS / ASA | 150.0 | 容易拉丝 / Stringing-prone |
| PA6CF / Nylon | 120.0 | 最容易拉丝 / Most stringing-prone |

---

## 验证 / Verification

导出 `.3mf` 后，用解压软件打开 `Metadata/plate_1.gcode`，搜 `G150.1`（H2D）或 `auto wipe` 注释，确认擦嘴次数和间隔符合预期。

After slicing, unzip the exported `.3mf` and open `Metadata/plate_1.gcode`. Search for `G150.1` (H2D) or `auto wipe` comments to confirm wipe count and interval.

---

## 注意事项 / Notes

- **Windows 下 Bambu Studio 可能弹"后处理脚本失败"错误框**：这是 Bambu 独占临时文件导致的，不影响最终打包的 .3mf 文件。点确认即可。
  On Windows, Bambu Studio may show a "post-processing script failed" dialog — this is caused by Bambu holding an exclusive lock on the temp G-code, **the packaged .3mf is still correct**. Just dismiss the dialog.
- **脚本不依赖第三方库**，纯 Python 标准库，任何系统都能跑。
  Zero dependencies — pure Python standard library, works on any OS with Python 3.8+.
- **macOS / Linux 下**同理，但 Bambu Studio 后处理字段要填正确的 Python 路径（用 `which python3` 查）。
  On macOS/Linux, use `which python3` to find the correct interpreter path.

---

## License

MIT
