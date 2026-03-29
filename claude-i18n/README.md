# claude-i18n‌​‍‌‍​‌​ — Claude Code 繁體中文化

一鍵將 Claude Code 全面中文化：指令說明、187 個思考動畫、完成提示、操作提示、互動按鍵提示、狀態訊息、錯誤訊息，全部翻譯成繁體中文。

支援 **npm 安裝版**與 **winget 原生安裝版**（`winget install Anthropic.ClaudeCode`）。

## 效果

### 指令說明中文化

（npm 版格式：`english(中文)`；winget 版保持純英文）

```
修改前：
/clear     Clear conversation history and free up context
/commit    Create a git commit
/compact   Clear conversation history but keep a summary

修改後（npm 版）：
/clear(清除)     清除對話紀錄，釋放上下文空間
/commit(提交)    建立 Git 提交
/compact(壓縮)   壓縮對話紀錄，保留摘要在上下文中

修改後（winget 版）：
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

### 互動提示 / 狀態 / 錯誤訊息中文化

```
修改前：Press Enter to continue          修改後：按 Enter 繼續
修改前：Esc to cancel                    修改後：Esc 取消
修改前：Waiting for permission…           修改後：等待權限中…
修改前：Context limit reached             修改後：上下文已滿
修改前：Sorry, Claude Code encountered... 修改後：抱歉，Claude Code 遇到錯誤
修改前：Do you want to proceed?           修改後：要繼續嗎？
修改前：(ctrl+o to expand)               修改後：(ctrl+o 展開)
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
- 指令名稱：npm 有 `english(中文)` 格式，winget 保持純英文（byte 限制）
- 思考動畫：187/187 全可替換（已優化翻譯長度）
- 其他類別：約 90% 可替換

如需 100% 覆蓋率，請使用 npm 版。

## 翻譯覆蓋率

| 類別 | npm 版 | winget 版 | 說明 |
|------|--------|-----------|------|
| 指令名稱 | 81 個 | — | winget 因 byte 限制保持英文 |
| 指令說明 | 74 個 | ~60 個 | winget 依字串長度判斷 |
| 思考動畫 | 187 個 | 187 個 | 已優化翻譯長度 |
| 完成提示 | 8 個 | ~5 個 | |
| 狀態/模板 | 5 個 | 5 個 | effort、expand、context 等 |
| 操作提示 | 2 個 | 2 個 | |
| 介面字串 | 94 個 | 90 個 | 互動提示、錯誤、確認、標籤 |

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

`claude-wrapper.py` 可作為 Claude Code 啟動器，提供兩項自動化功能：

1. **Claude Code 更新時自動重新 patch** — 偵測到 exe/cli.js 檔案變更時自動重新中文化
2. **翻譯包更新通知** — 每 24 小時檢查一次遠端是否有新版翻譯，有的話顯示提示（不強制更新）

```bash
# 設定 alias（替代 claude 指令）
alias claude="python /path/to/claude-wrapper.py"
```

啟動時如果有新版翻譯可用，會看到：

```
[claude-i18n] 新版翻譯 v2.2.0 可用（目前 v2.1.86）
[claude-i18n] 更新指令: cd /path/to/claude-i18n && git pull && python patch.py
```

- 每 24 小時最多檢查一次，不影響啟動速度
- 網路不通時靜默跳過，不會報錯
- 只是通知，不會自動拉取或修改任何檔案

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
