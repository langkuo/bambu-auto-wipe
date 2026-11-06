# bambu-auto-wipe

按挤出长度自动擦嘴的 Bambu Studio 后处理脚本。只在 infill 段触发，零表面影响。

## 支持机型

| 机型 | 自动检测 | 手动指定 |
|---|---|---|
| H2D | ✅ | `"H2D"` |
| A1 / A1 mini | ✅ | `"A1"` |
| P1P / P1S | ✅ | `"P1P"` |
| X1 / X1C | ✅ | `"X1C"` |

## 为什么需要这个脚本

Bambu Studio 没有"按累计挤出量触发擦嘴"的内置功能。默认的 purge wiper 只在换料或打印开头用一次，打大件中间喷嘴脏了、拉丝了，只能手动擦。

这个脚本会扫描完整 G-code，按你设定的挤出长度（默认 200mm）自动在 **infill 段中间**插入擦嘴动作，不打断外观面。

## 安装

### 1. 下载脚本

```bash
git clone https://github.com/yourname/bambu-auto-wipe.git
# 或直接下载 scripts/bambu_auto_wipe.py 和 config.json 到同一个文件夹
```

### 2. Bambu Studio 配置

**Printer Settings → General → Post-processing scripts**

填入完整路径（必须是解释器 + 脚本，不能只写 `python`）：

```
# Windows
C:\Python311\python.exe "C:\path\to\bambu-auto-wipe\scripts\bambu_auto_wipe.py"

# macOS
/usr/bin/python3 "/path/to/bambu-auto-wipe/scripts/bambu_auto_wipe.py"

# Linux
/usr/bin/python3 "/path/to/bambu-auto-wipe/scripts/bambu_auto_wipe.py"
```

### 3. 调参数（可选）

编辑同目录下的 `config.json`：

```json
{
  "wipe_every_mm": 200.0,     // 每挤出多少 mm 擦一次
  "only_infill": true,         // 只在 infill 段触发
  "retract_mm": 0.8,           // 擦前回抽量
  "restore_mm": 0.8,           // 擦后补压量
  "force_printer_model": null  // 自动检测；也可强制指定
}
```

### 参数调优表

| 耗材 | wipe_every_mm | 说明 |
|---|---|---|
| PLA | 300.0 | 几乎不拉丝，省时间 |
| PETG | 200.0 | 平衡防拉丝 vs 时间损失 |
| ABS / ASA | 150.0 | 容易拉丝 |
| PA6CF / 尼龙 | 120.0 | 最容易拉丝 |

## 验证

导出 `.3mf` 后，用解压软件打开 `Metadata/plate_1.gcode`，搜 `G150.1`（H2D）或 `auto wipe` 注释，确认擦嘴次数和间隔符合预期。

## 注意事项

- **Windows 下 Bambu Studio 可能弹"后处理脚本失败"错误框**：这是 Bambu 独占临时文件导致的，不影响最终打包的 .3mf 文件。点确认即可。
- **脚本不依赖第三方库**，纯 Python 标准库，任何系统都能跑。
- **macOS / Linux 下**同理，但 Bambu Studio 后处理字段要填正确的 Python 路径（`which python3`）。

## License

MIT
