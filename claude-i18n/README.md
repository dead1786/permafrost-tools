# claude-i18n — Claude Code 繁體中文化

一鍵將 Claude Code 全面中文化：78 個指令名稱與說明、187 個思考動畫、完成提示、操作提示，全部翻譯成繁體中文。

支援 **npm 安裝版**（cli.js）和**原生 .exe 版**（winget / standalone）。

## 效果

### 指令中文化

```
修改前：
/clear     Clear conversation history and free up context
/commit    Create a git commit
/compact   Clear conversation history but keep a summary

修改後：
/clear(清除)     清除對話紀錄，釋放上下文空間
/commit(提交)    建立 Git 提交
/compact(壓縮)   壓縮對話紀錄，保留摘要在上下文中
```

輸入 `/清除` 或 `/clear` 都能觸發同一個指令。

### 思考動畫中文化

```
修改前：Marinating…    修改後：醃漬中…
修改前：Moonwalking…   修改後：月球漫步中…
修改前：Crunching…     修改後：嘎吱嘎吱中…
```

### 完成提示中文化

```
修改前：Crunched for 2m 21s
修改後：運算了 耗時 2m 21s
```

### 操作提示中文化

```
修改前：Tip: Use /btw to ask a quick side question without interrupting Claude's current work
修改後：使用 /btw 快速問一個問題，不會中斷 Claude 目前的工作
```

## 安裝需求

- Python 3.8+
- Claude Code（npm 版或原生 .exe 版皆可）

## 使用方式

### npm 安裝版

```bash
# 套用中文化
python patch.py

# 預覽（不修改檔案）
python patch.py --dry-run

# 還原成英文
python patch.py --restore

# 掃描未翻譯的指令
python patch.py --scan

# 列出翻譯對照表
python patch.py --list
```

### 原生 .exe 版

```bash
# 套用中文化（需先關閉 Claude Code）
python patch.py --exe

# 預覽
python patch.py --exe --dry-run

# 還原
python patch.py --exe --restore
```

> **注意：** 原生版 patch 時必須先關閉 Claude Code，否則 .exe 會被鎖住無法寫入。Patch 完成後重新開啟即可。

## 翻譯覆蓋率

| 類別 | 數量 | 說明 |
|------|------|------|
| 指令名稱 | 78 個 | 格式：`english(中文)` |
| 指令說明 | 68 個 | 完整繁體中文翻譯 |
| 思考動畫 | 187 個 | 保留烹飪梗的惡趣味翻譯 |
| 完成提示 | 8 個 | Baked → 烘焙了、Crunched → 運算了 等 |
| 狀態文字 | 3 個 | for → 耗時、Idle → 閒置中 |
| 操作提示 | 2 個 | /clear 和 /btw 的使用提示 |

## 官方更新後怎麼辦？

1. 先還原：`python patch.py --restore`（或 `--exe --restore`）
2. 更新 Claude Code
3. 執行 `python patch.py --scan` 查看是否有新指令
4. 如果有新指令，在 `translations.json` 中新增翻譯
5. 重新套用：`python patch.py`（或 `--exe`）

## 新增語言

1. 複製 `translations.json` 為 `translations-ja.json`（以日文為例）
2. 將所有中文翻譯改為目標語言
3. 修改 `patch.py` 的 `TRANSLATIONS_FILE` 路徑
4. 執行 `python patch.py`

## 原理

純字串替換，不依賴正則表達式、不解析 AST、不猜測程式碼結構。

- **指令**：逐一替換 `name:"clear"` → `name:"clear(清除)"`
- **思考動畫**：整組陣列替換，187 個英文動詞 → 187 個中文動詞
- **完成提示 / 狀態 / Tips**：精確字串替換

穩定可靠，`str.replace()` 就完事了。

## License

MIT
