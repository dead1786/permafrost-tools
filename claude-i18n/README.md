# claude-i18n‌​‍‌‍​‌​ — Claude Code 繁體中文化

一鍵將 Claude Code 全面中文化：指令說明、187 個思考動畫、完成提示、操作提示，全部翻譯成繁體中文。

支援 **npm 安裝版**與 **winget 原生安裝版**（`winget install Anthropic.ClaudeCode`）。

## 效果

### 指令說明中文化

（指令名稱刻意保留英文，方便查資料時對照官方教學——詳見下方說明）

```
修改前：
/clear     Clear conversation history and free up context
/commit    Create a git commit
/compact   Clear conversation history but keep a summary

修改後：
/clear     清除對話紀錄，釋放上下文空間
/commit    建立 Git 提交
/compact   壓縮對話紀錄，保留摘要在上下文中
```

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
- Claude Code（擇一）：
  - **npm 版**：`npm install -g @anthropic-ai/claude-code`
  - **winget 版**：`winget install Anthropic.ClaudeCode`

## 使用方式

```bash
# 自動偵測（npm 優先，找不到就用 winget）
python patch.py

# 指定 npm 版
python patch.py --npm

# 指定 winget 版（原生 .exe）
python patch.py --winget

# 預覽（不修改檔案）
python patch.py --dry-run
python patch.py --dry-run --winget

# 還原成英文
python patch.py --restore
python patch.py --restore --winget

# 掃描未翻譯的指令（npm 版）
python patch.py --scan

# 列出翻譯對照表
python patch.py --list
```

## winget 版注意事項

winget 安裝的 Claude Code 是打包好的二進位檔（`claude.exe`）。中文字元的 byte 數比英文多，若中文版字串比原始英文字串更長則無法替換（自動跳過）。

因此 winget 版覆蓋率略低：
- 指令說明：約 60~70 個可替換
- 思考動畫：約 103/187 個可替換（較短的英文動詞沒辦法換）
- 部分完成提示：視字串長度而定

如需 100% 覆蓋率，請使用 npm 版。

## 翻譯覆蓋率

| 類別 | npm 版 | winget 版 | 說明 |
|------|--------|-----------|------|
| 指令說明 | 68 個 | ~60 個 | winget 依字串長度判斷 |
| 思考動畫 | 187 個 | ~103 個 | 中文 bytes 較長者跳過 |
| 完成提示 | 8 個 | ~5 個 | |
| 狀態文字 | 3 個 | ~2 個 | |
| 操作提示 | 2 個 | ~1 個 | |

## 官方更新後怎麼辦？

**npm 版：**
1. 先還原：`python patch.py --restore`
2. 更新 Claude Code：`npm update -g @anthropic-ai/claude-code`
3. 執行 `python patch.py --scan` 查看是否有新指令
4. 如果有新指令，在 `translations.json` 中新增翻譯
5. 重新套用：`python patch.py`

**winget 版：**
1. 更新 Claude Code：`winget upgrade Anthropic.ClaudeCode`（更新後需重新 patch）
2. 重新套用：`python patch.py --winget`
3. 備份檔為 `claude.exe.bak`，可用 `--restore --winget` 還原

## 自動維護（可選）

`claude-wrapper.py` 可作為 Claude Code 啟動器，偵測到版本更新時自動重新 patch：

```bash
# 設定 alias（替代 claude 指令）
alias claude="python /path/to/claude-wrapper.py"
```

## 為什麼指令名稱保持英文？

`/commit`、`/clear`、`/compact` 這些指令名稱刻意不翻譯，理由：

- **官方文件、教學影片、GitHub Issues 全用英文指令名**——遇到問題搜尋時用英文才找得到答案
- **指令說明已中文化**，`/commit` 旁邊寫著「建立 Git 提交」已足夠理解功能
- 把介面語言和查資料語言解耦，魚與熊掌都要

## 新增語言

1. 複製 `translations.json` 為 `translations-ja.json`（以日文為例）
2. 將所有中文翻譯改為目標語言
3. 修改 `patch.py` 的 `TRANSLATIONS_FILE` 路徑
4. 執行 `python patch.py`

## 原理

純字串替換，不依賴正則表達式、不解析 AST、不猜測程式碼結構。

- **指令說明**：逐一替換 `"Clear conversation history"` → `"清除對話紀錄，釋放上下文空間"`
- **思考動畫**：npm 版整組陣列替換；winget 版逐個動詞替換，超長跳過
- **完成提示 / 狀態 / Tips**：精確字串替換

穩定可靠，`str.replace()` 就完事了。

## License

MIT
