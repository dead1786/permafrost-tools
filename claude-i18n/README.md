# claude-i18n — Claude Code 指令中文化

一鍵將 Claude Code 的 55 個內建指令全部翻譯成繁體中文。名稱與說明都會翻譯，英文和中文指令都能觸發。

## 安裝需求

- Python 3.8+
- Claude Code（npm 安裝版）：`npm install -g @anthropic-ai/claude-code`

> **注意：** 獨立 `.exe` 版本無法 patch。必須使用 npm 安裝的版本。

## 使用方式

```bash
# 套用中文化
python patch.py

# 預覽（不修改檔案）
python patch.py --dry-run

# 還原成英文
python patch.py --restore

# 掃描未翻譯的指令（官方更新後使用）
python patch.py --scan

# 列出翻譯對照表
python patch.py --list
```

## 效果

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

輸入 `/清除` 或 `/clear` 都能執行同一個指令。

## 翻譯覆蓋率

- **55/55** 個內建指令（100%）
- 名稱格式：`english(中文)`
- 說明：完整繁體中文翻譯
- 別名：中文和英文都能觸發

## 官方更新後怎麼辦？

1. Claude Code 更新後，先執行 `python patch.py --restore` 還原
2. 更新 Claude Code（`npm update -g @anthropic-ai/claude-code`）
3. 執行 `python patch.py --scan` 查看是否有新指令
4. 如果有新指令，在 `translations.json` 中新增翻譯
5. 執行 `python patch.py` 重新套用

## 新增語言

1. 複製 `translations.json` 為 `translations-ja.json`（以日文為例）
2. 將所有中文翻譯改為日文
3. 修改 `patch.py` 的 `TRANSLATIONS_FILE` 路徑
4. 執行 `python patch.py`

## 原理

純字串替換。`translations.json` 是一個 key-value 對照表：

```json
{
  "names": {
    "name:\"clear\"": "name:\"clear(清除)\""
  },
  "descriptions": {
    "\"Clear conversation history and free up context\"": "\"清除對話紀錄，釋放上下文空間\""
  }
}
```

不依賴正則表達式、不解析 AST、不猜測程式碼結構。簡單的 `str.replace()`，穩定可靠。

## License

MIT
