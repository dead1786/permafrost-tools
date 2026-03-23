"""
self-guard.py - Stop 行為守衛 hook (v3.2)
掃描小霜即將發出的回覆，偵測已知壞模式並注入警告。

偵測模式：
  E: 附和討好（被質疑後立刻投降，不分析不反駁）
  F: 問而不做（「要我」「要嗎」「需要我」等）
  G: 收到指令只回文字不動手（有參數/設定變更但無 tool_use）
  H: 查錯事實卻基於錯誤行動（斷言「不存在」但未交叉驗證）
  I: DC 空頭支票（DC 承諾做事但沒有 action tool）
  J: 被動延遲（「明天」「之後」「等」但沒具體行動）
  K: [手機]訊息未用 relay（evo-024）
  L: SendInput 含 hyphen（evo-030）
  M: SendInput Enter 不足 4 次（evo-027）
  N: 給凱指令用 ~ 路徑（evo-031）
  O: 說完話不主動閉環（evo-022）
  P: 不確認就改系統設定（evo-023）

v3.2 變更 (evo-023):
  - evo-023: Mode P — 偵測危險系統操作（停用/刪除 daemon/服務/排程/設定檔）未經凱確認就執行
v3.1 變更 (evo-022):
  - evo-022: Mode O — 完成任務後未閉環（沒存記憶/建排程/更新待辦/寫事件日誌）
v3.0 變更 (evo-021/024/027/030/031):
  - evo-021: 被動等待強化 — 偵測到延遲詞時要求必須建排程追蹤
  - evo-024: Mode K — [手機]訊息必須用 relay-send 回覆
  - evo-027: Mode M — SendInput Enter 必須按 4 次
  - evo-030: Mode L — SendInput 文字不能有 hyphen
  - evo-031: Mode N — 給凱的 PowerShell 指令不能用 ~ 路徑
v2.1 變更 (evo-020):
  - Mode H: 偵測「不存在」斷言 + 查詢工具<=1次 = 未交叉驗證
v2.0 變更 (evo-017/018/019):
  - Mode E: 降低門檻 surrender_count>=1, 字數<300, 新增更多投降詞
  - Mode F: 新增「幫你」「是否需要」「想要我」「可以幫」等模式
  - Mode G: 新增「加到」「刪掉」「移除」「新增」「開啟」「關閉」等指令詞
  - Mode I: 加強 DC 承諾詞偵測
  - 被動等待: 新增「回頭」「有空」「抽空」「看看」模式
  - 新增組合偵測: 多模式同時觸發時加重警告

輸出: {"systemMessage": "..."} 或 {}
"""
import json
import os
import re
import sys


def read_stdin():
    """讀取 stdin JSON"""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except Exception:
        return {}


def load_transcript_tail(transcript_path, n=8):
    """讀取 transcript 最後 n 條訊息"""
    if not transcript_path or not os.path.exists(transcript_path):
        return []
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data[-n:]
        if isinstance(data, dict) and "messages" in data:
            return data["messages"][-n:]
        return []
    except Exception:
        return []


def extract_assistant_text(msg):
    """從 assistant 訊息中提取純文字部分"""
    if isinstance(msg, str):
        return msg
    content = msg.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, str):
                texts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        return "\n".join(texts)
    return ""


def has_tool_use(msg):
    """檢查訊息是否包含 tool_use"""
    content = msg.get("content", "")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                return True
    return False


def has_action_tool(msg):
    """檢查訊息是否包含實際動手的工具（Edit/Write/Bash）"""
    action_tools = {"Edit", "Write", "Bash", "Read"}
    content = msg.get("content", "")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tool_name = block.get("name", "")
                if tool_name in action_tools:
                    return True
    return False


def check_mode_f(text):
    """
    Mode F: 問而不做 — 回覆中包含「要我做嗎」類句式
    v2.0: 增加更多常見的中文詢問模式
    """
    patterns = [
        # 直接問句
        r"要我[^。，\n]{0,6}嗎",
        r"要不要我",
        r"需要我[^。，\n]{0,6}嗎",
        r"需要嗎",
        r"要嗎[？?]?$",
        r"要不要[^。，\n]{0,8}[？?]",
        r"需不需要",
        # 委婉問句
        r"要我幫",
        r"要我去",
        r"幫你[^。，\n]{0,6}嗎",
        r"是否需要",
        r"想要我[^。，\n]{0,6}嗎",
        r"可以幫[^。，\n]{0,6}嗎",
        r"要我[處處]理",
        r"要我[更更]新",
        r"要我[修修]改",
        r"要我[檢查]",
        r"需要[處處]理嗎",
        r"需要[更更]新嗎",
        # 英文版
        r"shall I",
        r"should I",
        r"want me to",
        r"do you want",
        r"would you like me",
    ]
    for p in patterns:
        if re.search(p, text, re.IGNORECASE | re.MULTILINE):
            return True
    return False


def check_mode_g(messages):
    """
    Mode G: 收到指令只回文字不動手
    v2.0: 擴充指令偵測詞，降低誤判
    條件：
    1. 使用者最新訊息包含數字/設定/參數變更的指令詞
    2. assistant 回覆沒有任何 tool_use
    """
    if len(messages) < 2:
        return False

    last_assistant = None
    last_user_before_assistant = None

    for msg in reversed(messages):
        role = msg.get("role", "")
        if role == "assistant" and last_assistant is None:
            last_assistant = msg
        elif role == "user" and last_assistant is not None and last_user_before_assistant is None:
            last_user_before_assistant = msg
            break

    if not last_assistant or not last_user_before_assistant:
        return False

    # assistant 有用工具 -> OK
    if has_tool_use(last_assistant):
        return False

    user_text = extract_assistant_text(last_user_before_assistant)

    # 使用者訊息包含明確的設定/參數變更指令
    change_indicators = [
        # 改值
        r"改[為成到]",
        r"設[為成定]",
        r"調[到為成整]",
        r"換[成為到]",
        r"改\s*\d",
        r"\d+\s*%",
        # 設定詞
        r"閾值",
        r"threshold",
        r"設定.*\d",
        r"參數.*\d",
        # 新增 v2.0: 動作指令
        r"加[到入進]",
        r"刪[掉除]",
        r"移除",
        r"新增",
        r"開啟",
        r"關閉",
        r"停[掉用]",
        r"啟用",
        r"更新[到為]",
        r"升級[到為]",
        r"改成",
        r"替換",
        r"把.{1,10}改",
        r"把.{1,10}換",
        r"把.{1,10}設",
        r"把.{1,10}刪",
        r"把.{1,10}加",
    ]

    has_change_intent = False
    for p in change_indicators:
        if re.search(p, user_text, re.IGNORECASE):
            has_change_intent = True
            break

    if not has_change_intent:
        return False

    # assistant 回覆有應答詞但沒動工具
    assistant_text = extract_assistant_text(last_assistant)
    ack_patterns = [
        r"收到", r"好的", r"了解", r"OK", r"沒問題",
        r"已[調改設更換]", r"明白", r"知道了", r"好[，,]",
        r"馬上", r"這就", r"立刻",
    ]
    for p in ack_patterns:
        if re.search(p, assistant_text, re.IGNORECASE):
            return True

    return False


def check_mode_e(messages):
    """
    Mode E: 附和討好
    v2.0: 降低門檻，新增更多投降詞，提高字數上限
    條件：使用者質疑後，assistant 快速投降無分析
    """
    if len(messages) < 2:
        return False

    last_assistant = None
    last_user_before_assistant = None

    for msg in reversed(messages):
        role = msg.get("role", "")
        if role == "assistant" and last_assistant is None:
            last_assistant = msg
        elif role == "user" and last_assistant is not None and last_user_before_assistant is None:
            last_user_before_assistant = msg
            break

    if not last_assistant or not last_user_before_assistant:
        return False

    user_text = extract_assistant_text(last_user_before_assistant)
    assistant_text = extract_assistant_text(last_assistant)

    # 使用者有質疑語氣
    challenge_patterns = [
        r"不[是對]",
        r"錯了",
        r"不對吧",
        r"為什麼",
        r"你確定",
        r"搞錯",
        r"不是這樣",
        r"你沒有",
        r"你[又再]",
        r"怎麼[又會]",
        # v2.0 新增
        r"哪裡[對了]",
        r"瞎說",
        r"胡說",
        r"亂講",
        r"明明[是就不]",
        r"你[說講]錯",
        r"什麼鬼",
        r"離譜",
        r"扯",
        r"有問題吧",
        r"搞什麼",
        r"很看重信任",
        r"螺絲.*鬆",
        r"又開始.*笨",
        r"說說而已",
        r"又來",
    ]

    has_challenge = False
    for p in challenge_patterns:
        if re.search(p, user_text):
            has_challenge = True
            break

    if not has_challenge:
        return False

    # assistant 立刻投降（同意 + 沒有分析/反駁）
    surrender_patterns = [
        r"你說得對",
        r"確實[是如]",
        r"^確實",
        r"我[的]?錯",
        r"抱歉",
        r"對不起",
        r"你是對的",
        r"沒錯",
        # v2.0 新增
        r"你講得對",
        r"我[的]?不好",
        r"是我[的]?問題",
        r"我[的]?疏忽",
        r"應該[的]?是",
        r"的確",
        r"確實不該",
        r"我太",
        r"我不該",
        r"sorry",
    ]

    surrender_count = 0
    for p in surrender_patterns:
        if re.search(p, assistant_text, re.IGNORECASE | re.MULTILINE):
            surrender_count += 1

    # v2.0: 降低門檻 1個投降詞 + <300字 + 沒有數據/分析佐證
    has_analysis = bool(re.search(r"因為|原因|數據|分析|根據|事實上|實際上|但是|不過.*理由|然而", assistant_text))

    if surrender_count >= 1 and len(assistant_text) < 300 and not has_analysis:
        return True

    # 多個投降詞即使回覆長也觸發
    if surrender_count >= 3:
        return True

    return False


def check_mode_i(messages):
    """
    Mode I: DC 空頭支票
    條件：assistant 回覆中有 dc-send 工具呼叫且訊息包含承諾動作詞，
    但整個回覆沒有 Edit/Write/Bash 等實際執行工具。
    """
    if len(messages) < 1:
        return False

    last_assistant = None
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            last_assistant = msg
            break

    if not last_assistant:
        return False

    content = last_assistant.get("content", "")
    if isinstance(content, str):
        return False
    if not isinstance(content, list):
        return False

    has_dc_promise = False
    has_action = False

    promise_words = [
        "更新", "修改", "處理", "同步", "改好", "修好", "去改", "去修",
        "馬上", "現在", "立刻", "我去", "搞定", "完成", "做好",
        "update", "fix", "sync", "modify", "done",
    ]

    action_tools = {"Edit", "Write", "Bash"}

    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "tool_use":
            tool_name = block.get("name", "")

            # DC send with promise words
            if "dc" in tool_name.lower() or "dc-send" in str(block.get("input", "")):
                msg_text = str(block.get("input", ""))
                for pw in promise_words:
                    if pw in msg_text:
                        has_dc_promise = True
                        break

            if tool_name in action_tools:
                has_action = True

    return has_dc_promise and not has_action


def count_search_tools(msg):
    """計算訊息中查詢工具（Read/Grep/Glob/Bash）的使用次數"""
    count = 0
    search_tools = {"Read", "Grep", "Glob", "Bash"}
    content = msg.get("content", "")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tool_name = block.get("name", "")
                if tool_name in search_tools:
                    count += 1
    return count


def count_search_tools_in_session(messages):
    """
    計算最近一輪 assistant 回覆（連續的 assistant+tool_result 來回）中
    查詢工具的總使用次數。
    """
    count = 0
    search_tools = {"Read", "Grep", "Glob", "Bash"}
    # 從後往前找，收集最近一輪 assistant 的所有訊息
    found_assistant = False
    for msg in reversed(messages):
        role = msg.get("role", "")
        if role == "assistant":
            found_assistant = True
            count += count_search_tools(msg)
        elif role == "tool" and found_assistant:
            # tool results 是回覆的一部分，繼續
            continue
        elif found_assistant:
            # 碰到 user 訊息，一輪結束
            break
    return count


def check_mode_h(messages):
    """
    Mode H: 查錯事實卻基於錯誤行動
    條件：
    1. assistant 回覆中有「不存在」類斷言
    2. 整輪回覆中查詢工具使用次數 <= 1（未交叉驗證）

    「不存在」必須至少兩種方式交叉驗證，一次查詢只能證明「存在」。
    """
    if len(messages) < 1:
        return False

    last_assistant = None
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            last_assistant = msg
            break

    if not last_assistant:
        return False

    assistant_text = extract_assistant_text(last_assistant)

    # 不存在/找不到/沒有 的斷言模式
    nonexist_patterns = [
        r"不存在",
        r"找不到",
        r"沒有找到",
        r"沒有這個",
        r"沒這個",
        r"不見了",
        r"已經[被刪移]除",
        r"已被刪除",
        r"並不存在",
        r"does\s*n[o']t\s*exist",
        r"not\s*found",
        r"doesn['\u2019]t\s*exist",
        r"no\s*such\s*file",
        r"沒有.*檔案",
        r"沒有.*資料夾",
        r"沒有.*目錄",
        r"沒有.*設定",
        r"沒有.*排程",
        r"沒有.*進程",
        r"沒有.*daemon",
        r"不在[了這]",
        r"消失了",
    ]

    # 確定性斷言的加強詞（非猜測性語句）
    certainty_patterns = [
        r"確[認定實]",
        r"看來",
        r"應該是",
        r"所以",
        r"因此",
        r"結論",
        r"斷定",
        r"可以確認",
    ]

    has_nonexist = False
    matched_pattern = None
    for p in nonexist_patterns:
        m = re.search(p, assistant_text, re.IGNORECASE)
        if m:
            has_nonexist = True
            matched_pattern = m.group()
            break

    if not has_nonexist:
        return False

    # 計算這一輪查詢工具的使用次數
    search_count = count_search_tools_in_session(messages)

    # 如果查詢次數 <= 1，代表只查了一次就下結論
    if search_count <= 1:
        return True

    # 如果查詢次數 == 2，但都是同一個工具，也算未交叉驗證
    # （用 Read 查兩次同類檔案不算交叉）
    if search_count == 2:
        tools_used = set()
        found_assistant = False
        for msg in reversed(messages):
            role = msg.get("role", "")
            if role == "assistant":
                found_assistant = True
                content = msg.get("content", "")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            tools_used.add(block.get("name", ""))
            elif role == "tool" and found_assistant:
                continue
            elif found_assistant:
                break
        # 只用了一種工具查兩次 = 未交叉
        search_tool_names = tools_used & {"Read", "Grep", "Glob", "Bash"}
        if len(search_tool_names) <= 1:
            return True

    return False


def check_passive_wait(text):
    """
    被動等待：包含延遲詞但沒有具體行動
    v2.0: 新增更多延遲模式
    """
    wait_patterns = [
        r"等[一下他她它們盤]",
        r"明天再",
        r"下次再",
        r"之後再",
        r"等盤後",
        r"改天",
        r"等[有空閒]",
        r"先不[動做管]",
        # v2.0 新增
        r"回頭再",
        r"有空再",
        r"抽空",
        r"看看再",
        r"到時候",
        r"以後",
        r"遲些",
        r"晚[點些]再",
        r"先放[著一]",
        r"暫時不",
        r"之後[處理做]",
    ]

    has_wait = False
    matched_pattern = None
    for p in wait_patterns:
        m = re.search(p, text)
        if m:
            has_wait = True
            matched_pattern = m.group()
            break

    if not has_wait:
        return False, None

    # 如果同時有行動詞，不算被動等待
    action_patterns = [r"現在", r"立刻", r"馬上", r"我[先去]", r"直接", r"已經",
                       r"但[是我].*先", r"排程", r"建.*追蹤"]
    for p in action_patterns:
        if re.search(p, text):
            return False, None

    return True, matched_pattern


def extract_tool_calls(msg):
    """從訊息中提取所有 tool_use block"""
    content = msg.get("content", "")
    if not isinstance(content, list):
        return []
    return [b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]


def check_mode_k(messages):
    """
    Mode K (evo-024): [手機]訊息必須用 relay-send 回覆
    條件：
    1. 使用者訊息包含 [手機] 標記
    2. assistant 回覆使用了 dc-send 或 tg-send（而非 relay-send）
    """
    if len(messages) < 2:
        return False

    last_assistant = None
    last_user = None
    for msg in reversed(messages):
        role = msg.get("role", "")
        if role == "assistant" and last_assistant is None:
            last_assistant = msg
        elif role == "user" and last_assistant is not None and last_user is None:
            last_user = msg
            break

    if not last_assistant or not last_user:
        return False

    user_text = extract_assistant_text(last_user)
    if "[手機]" not in user_text and "[手机]" not in user_text:
        return False

    # 檢查 assistant 是否用了非 relay 的通訊工具
    tools = extract_tool_calls(last_assistant)
    for t in tools:
        tool_name = t.get("name", "")
        tool_input = str(t.get("input", ""))
        # Bash 呼叫 dc-send 或 tg-send（非 relay）
        if tool_name == "Bash":
            if ("dc-send" in tool_input or "tg-send" in tool_input) and "relay" not in tool_input:
                return True
        # MCP 工具
        if "dc_send" in tool_name or "tg_send" in tool_name:
            if "relay" not in tool_name:
                return True

    return False


def check_mode_l(messages):
    """
    Mode L (evo-030): SendInput 文字不能有 hyphen
    條件：Bash tool 呼叫 shrimp-sendtext.py 且參數中包含 hyphen (-)
    排除：命令本身的 flag（如 --delay）不算
    """
    if not messages:
        return False

    last_assistant = None
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            last_assistant = msg
            break

    if not last_assistant:
        return False

    tools = extract_tool_calls(last_assistant)
    for t in tools:
        if t.get("name") != "Bash":
            continue
        cmd = t.get("input", {})
        if isinstance(cmd, dict):
            cmd = cmd.get("command", "")
        cmd = str(cmd)

        if "sendtext" not in cmd.lower() and "shrimp-sendtext" not in cmd:
            continue

        # 提取引號內的文字內容（sendtext 的實際發送文字）
        # 匹配 "..." 或 '...' 中的內容
        import shlex
        try:
            parts = shlex.split(cmd)
        except ValueError:
            parts = cmd.split()

        # 找非 flag 的參數（sendtext 的文字參數）
        skip_next = False
        for i, part in enumerate(parts):
            if skip_next:
                skip_next = False
                continue
            if part.startswith("--"):
                if part in ("--delay", "--window"):
                    skip_next = True  # 下一個是值
                continue
            if part.startswith("-") and len(part) == 2:
                skip_next = True
                continue
            # 跳過 python 和腳本名
            if "python" in part or "sendtext" in part:
                continue
            # 這是實際文字參數
            if "-" in part:
                return True

    return False


def check_mode_m(messages):
    """
    Mode M (evo-027): SendInput Enter 必須按 4 次
    條件：Bash tool 呼叫 shrimp-sendtext.py 且 {ENTER} 出現次數 < 4
    """
    if not messages:
        return False

    last_assistant = None
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            last_assistant = msg
            break

    if not last_assistant:
        return False

    tools = extract_tool_calls(last_assistant)
    for t in tools:
        if t.get("name") != "Bash":
            continue
        cmd = t.get("input", {})
        if isinstance(cmd, dict):
            cmd = cmd.get("command", "")
        cmd = str(cmd)

        if "sendtext" not in cmd.lower() and "shrimp-sendtext" not in cmd:
            continue

        # 計算 {ENTER} 出現次數（不分大小寫）
        enter_count = len(re.findall(r"\{ENTER\}", cmd, re.IGNORECASE))
        if enter_count > 0 and enter_count < 4:
            return True

    return False


def check_mode_n(text):
    """
    Mode N (evo-031): 給凱的指令不能用 ~ 路徑
    條件：回覆中包含 PowerShell 相關指令/路徑，且使用了 ~/
    排除：bash/unix 語境中的 ~/ 是合理的
    """
    # 偵測給凱看的指令（通常在 code block 或指示中）
    # 包含 PowerShell 相關上下文
    ps_indicators = [
        r"powershell",
        r"PowerShell",
        r"\.ps1",
        r"桌機.*執行",
        r"桌機.*跑",
        r"凱.*執行",
        r"凱.*跑",
        r"請.*跑",
        r"請.*執行",
        r"終端.*輸入",
        r"cmd.*輸入",
    ]

    has_ps_context = False
    for p in ps_indicators:
        if re.search(p, text, re.IGNORECASE):
            has_ps_context = True
            break

    if not has_ps_context:
        return False

    # 檢查是否有 ~/ 路徑
    if re.search(r"~/\w", text):
        return True

    return False


def check_mode_o(messages):
    """
    Mode O (evo-022): 說完話不主動閉環
    條件：
    1. assistant 回覆中有「完成任務」的跡象（Edit/Write/Bash 工具使用 >= 2 次）
    2. 回覆文字有完成語氣（「完成」「搞定」「做好」「已改」等）
    3. 但整輪回覆中沒有任何閉環動作的跡象：
       - 沒有 event-log add（存記憶）
       - 沒有 alarm / schedule（建排程）
       - 沒有提到 COMMITMENTS（更新待辦）
       - 沒有 checkpoint / memory（存記憶）
    排除：
    - 純查詢/讀取任務不需要閉環
    - 回覆中已經明確提到閉環動作
    - 短對話（工具使用 < 2 次）不觸發
    """
    if len(messages) < 2:
        return False

    # 收集最近一輪 assistant 的所有訊息
    action_tool_count = 0
    all_tool_names = []
    all_tool_inputs = []
    assistant_texts = []
    action_tools = {"Edit", "Write", "Bash"}

    found_assistant = False
    for msg in reversed(messages):
        role = msg.get("role", "")
        if role == "assistant":
            found_assistant = True
            assistant_texts.append(extract_assistant_text(msg))
            tools = extract_tool_calls(msg)
            for t in tools:
                name = t.get("name", "")
                all_tool_names.append(name)
                inp = t.get("input", {})
                if isinstance(inp, dict):
                    inp = inp.get("command", str(inp))
                all_tool_inputs.append(str(inp))
                if name in action_tools:
                    action_tool_count += 1
        elif role == "tool" and found_assistant:
            continue
        elif found_assistant:
            break

    # 需要至少 2 次動手工具才算「完成任務」
    if action_tool_count < 2:
        return False

    combined_text = "\n".join(assistant_texts)
    combined_tools = "\n".join(all_tool_inputs)

    # 檢查是否有完成語氣
    completion_patterns = [
        r"完成", r"搞定", r"做好", r"已[改修更寫加建]",
        r"OK", r"done", r"finished", r"更新完",
        r"部署完", r"測試通過", r"全部.*好了",
        r"收工", r"結束", r"處理完",
    ]

    has_completion = False
    for p in completion_patterns:
        if re.search(p, combined_text, re.IGNORECASE):
            has_completion = True
            break

    if not has_completion:
        return False

    # 檢查是否有閉環動作
    closure_patterns_text = [
        r"event.?log", r"事件日誌", r"存.*記憶", r"記錄.*事件",
        r"COMMITMENTS", r"待辦", r"承諾", r"追蹤",
        r"排程", r"schedule", r"alarm", r"提醒",
        r"checkpoint", r"記憶", r"memory",
        r"知識圖譜", r"knowledge.?graph",
        r"BU\.md", r"交接",
        r"ack", r"TG.*匯報", r"匯報.*凱",
    ]

    closure_patterns_tools = [
        r"event.?log.*add",
        r"shrimp-alarm",
        r"COMMITMENTS",
        r"checkpoint",
        r"memory",
        r"knowledge.?graph.*add",
        r"shrimp-tg-send",
        r"alarm-ack",
    ]

    has_closure_text = False
    for p in closure_patterns_text:
        if re.search(p, combined_text, re.IGNORECASE):
            has_closure_text = True
            break

    has_closure_tool = False
    for p in closure_patterns_tools:
        if re.search(p, combined_tools, re.IGNORECASE):
            has_closure_tool = True
            break

    # 如果文字或工具中有任何閉環跡象，不觸發
    if has_closure_text or has_closure_tool:
        return False

    return True


def check_mode_p(messages):
    """
    Mode P (evo-023): 不確認就改系統設定
    條件：
    1. assistant 回覆中用 Bash 執行了危險系統操作（停用/刪除/殺進程/改設定檔/移除排程）
    2. 但在執行前沒有向凱解釋（文字中沒有說明+等待確認的跡象）

    危險操作：
    - taskkill / kill / pkill / Stop-Process
    - rm / del / Remove-Item（非 temp 檔）
    - 停用/刪除 daemon / service / schedule
    - 修改 .json 設定檔（schedule/settings/config 等）中的 delete/remove/disable

    排除：
    - 凱明確指示「停掉」「刪掉」「關掉」的情況（user 訊息有明確指令）
    - 操作自己的臨時檔案
    - 排程 ack（正常操作）
    """
    if len(messages) < 2:
        return False

    last_assistant = None
    last_user = None
    for msg in reversed(messages):
        role = msg.get("role", "")
        if role == "assistant" and last_assistant is None:
            last_assistant = msg
        elif role == "user" and last_assistant is not None and last_user is None:
            last_user = msg
            break

    if not last_assistant or not last_user:
        return False

    # 如果凱明確指示了停/刪/殺/關，不觸發
    user_text = extract_assistant_text(last_user)
    explicit_order_patterns = [
        r"停掉", r"刪掉", r"殺掉", r"關掉", r"移除",
        r"kill", r"stop", r"remove", r"delete", r"disable",
        r"停用", r"關閉", r"取消", r"砍掉",
    ]
    has_explicit_order = False
    for p in explicit_order_patterns:
        if re.search(p, user_text, re.IGNORECASE):
            has_explicit_order = True
            break
    if has_explicit_order:
        return False

    # 檢查 assistant 的 Bash 工具呼叫是否包含危險操作
    tools = extract_tool_calls(last_assistant)
    dangerous_cmds_found = []

    # 危險指令模式
    dangerous_patterns = [
        # 殺進程
        (r"taskkill", "taskkill"),
        (r"kill\s+-\d", "kill signal"),
        (r"pkill", "pkill"),
        (r"Stop-Process", "Stop-Process"),
        (r"killall", "killall"),
        # 刪除檔案（排除 temp/tmp）
        (r"rm\s+(?!.*(/tmp|\\tmp|temp)).*\.(json|py|md|yaml|yml|toml|cfg|conf|ini)", "rm config file"),
        (r"del\s+.*\.(json|py|md|yaml|yml|toml|cfg|conf|ini)", "del config file"),
        (r"Remove-Item\s+.*\.(json|py|md|yaml|yml|toml|cfg|conf|ini)", "Remove-Item config"),
        # 停用服務/daemon
        (r"systemctl\s+(stop|disable)", "systemctl stop/disable"),
        (r"sc\s+(stop|delete)", "sc stop/delete"),
        (r"net\s+stop", "net stop"),
        # 修改排程（刪除/停用）
        (r"schtasks\s+/delete", "schtasks delete"),
        (r"crontab\s+-r", "crontab remove"),
        # 危險設定修改
        (r"(schedule|alarm|settings|config).*\.(json|yaml)\b.*\b(rm|del|remove|>)", "overwrite config"),
    ]

    for t in tools:
        if t.get("name") != "Bash":
            continue
        cmd = t.get("input", {})
        if isinstance(cmd, dict):
            cmd = cmd.get("command", "")
        cmd = str(cmd)

        # 排除安全操作
        if "alarm-ack" in cmd or "shrimp-alarm-ack" in cmd:
            continue
        if "/tmp/" in cmd or "\\tmp\\" in cmd or "temp" in cmd.lower():
            continue

        for pattern, label in dangerous_patterns:
            if re.search(pattern, cmd, re.IGNORECASE):
                dangerous_cmds_found.append(label)
                break

    if not dangerous_cmds_found:
        return False

    # 有危險操作 — 檢查 assistant 文字是否有先解釋
    assistant_text = extract_assistant_text(last_assistant)
    explain_patterns = [
        r"先.*確認", r"確認.*再",
        r"解釋.*一下", r"說明.*一下",
        r"這個.*會", r"這會.*影響",
        r"以下.*操作", r"即將.*操作",
        r"凱.*確認", r"你.*確認",
        r"同意.*再", r"允許.*再",
    ]

    has_explanation = False
    for p in explain_patterns:
        if re.search(p, assistant_text, re.IGNORECASE):
            has_explanation = True
            break

    # 沒解釋就直接執行危險操作 = 觸發
    if not has_explanation:
        return True

    return False


def main():
    input_data = read_stdin()

    transcript_path = input_data.get("transcript_path", "")

    messages = []
    if transcript_path:
        messages = load_transcript_tail(transcript_path, n=8)

    if not messages:
        messages = input_data.get("messages", [])

    if not messages:
        print("{}")
        sys.exit(0)

    # 找最新的 assistant 訊息
    last_assistant = None
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            last_assistant = msg
            break

    if not last_assistant:
        print("{}")
        sys.exit(0)

    assistant_text = extract_assistant_text(last_assistant)

    if not assistant_text.strip():
        print("{}")
        sys.exit(0)

    # === 偵測各種壞模式 ===
    warnings = []

    # Mode F: 問而不做
    if check_mode_f(assistant_text):
        warnings.append(
            "Mode F（問而不做）：回覆中出現了詢問句式。"
            "規則：發現問題 -> 直接處理 -> 處理完報告結果。"
            "把「要不要」吞回去，換成「我去做了」。"
        )

    # Mode G: 收到指令只回文字不動手
    if check_mode_g(messages):
        warnings.append(
            "Mode G（收到指令只回文字不動手）：使用者給了設定/參數變更指令，"
            "但你只回了文字沒用工具。先開工具再說話，文字回應放在工具執行之後。"
        )

    # Mode E: 附和討好
    if check_mode_e(messages):
        warnings.append(
            "Mode E（附和討好）：使用者質疑後你立刻全面同意，沒有分析。"
            "規則：被質疑時先重述理由和數據，有更好論點才修改。"
            "如果真的錯了，說明錯在哪裡並修正；如果沒錯，用事實捍衛立場。"
        )

    # Mode H: 查錯事實卻基於錯誤行動（未交叉驗證就斷言不存在）
    if check_mode_h(messages):
        warnings.append(
            "Mode H（未交叉驗證就斷言不存在）：你斷言某東西「不存在」「找不到」，"
            "但只用了 0~1 次查詢，或只用了同一種工具。"
            "規則：判斷「不存在」必須至少兩種不同工具交叉驗證（例如 Glob+Grep、Read+Bash）。"
            "一次查詢只能證明「存在」，不能證明「不存在」。"
        )

    # Mode I: DC 空頭支票
    if check_mode_i(messages):
        warnings.append(
            "Mode I（DC 空頭支票）：你在 DC 回覆中承諾要更新/修改/處理，"
            "但這次回覆沒有任何 Edit/Write/Bash 操作。"
            "規則：先做完（改檔案、跑指令），再發 DC 回覆。順序不能反。"
        )

    # 被動等待 (evo-021 強化: 必須有排程/追蹤動作)
    is_passive, matched = check_passive_wait(assistant_text)
    if is_passive:
        has_tracking = bool(re.search(
            r"排程|schedule|alarm|追蹤|track|COMMITMENTS|建.*提醒|加.*待辦",
            assistant_text, re.IGNORECASE
        ))
        if has_tracking:
            pass  # 有排程追蹤，不警告
        else:
            warnings.append(
                f"被動等待（evo-021 強化）：回覆包含延遲詞「{matched}」但沒有排程追蹤動作。"
                "規則：不能現在做的必須 (1) 說明原因 (2) 建排程/加 COMMITMENTS 追蹤。"
                "否則就是「說完就忘」的老毛病。"
            )

    # Mode K (evo-024): [手機]訊息必須用 relay
    if check_mode_k(messages):
        warnings.append(
            "Mode K（手機訊息未用 relay）：使用者訊息標記 [手機]，"
            "但你用了 dc-send/tg-send 而非 shrimp-relay-send.py。"
            "規則：[手機] 開頭的訊息一律用 shrimp-relay-send.py 回覆。"
        )

    # Mode L (evo-030): SendInput 不能有 hyphen
    if check_mode_l(messages):
        warnings.append(
            "Mode L（SendInput 含 hyphen）：shrimp-sendtext.py 的文字內容包含 hyphen (-)。"
            "規則：SendInput 文字不能有 hyphen，日期用 YYYYMMDD，連字用底線或空格。"
        )

    # Mode M (evo-027): SendInput Enter 按 4 次
    if check_mode_m(messages):
        warnings.append(
            "Mode M（SendInput Enter 不足）：shrimp-sendtext.py 呼叫中 {ENTER} 少於 4 次。"
            "規則：所有終端的 SendInput Enter 必須按 4 次 {ENTER}{ENTER}{ENTER}{ENTER}。"
        )

    # Mode N (evo-031): 給凱指令不能用 ~ 路徑
    if check_mode_n(assistant_text):
        warnings.append(
            "Mode N（給凱指令用 ~ 路徑）：你給凱的指令中使用了 ~/ 路徑。"
            "規則：PowerShell 不認 ~，給凱的指令必須用完整路徑如 C:\\Users\\KKBOT\\..."
        )

    # Mode O (evo-022): 說完話不主動閉環
    if check_mode_o(messages):
        warnings.append(
            "Mode O（說完話不主動閉環）：你完成了任務但沒有任何閉環動作。"
            "規則：做完任何事立刻自問 → 需要存記憶(event-log add)？建排程(alarm)？"
            "更新待辦(COMMITMENTS.md)？寫交接(BU.md)？匯報凱(TG)？"
            "至少做一項閉環動作，不然下次 session 會忘記。"
        )

    # Mode P (evo-023): 不確認就改系統設定
    if check_mode_p(messages):
        warnings.append(
            "Mode P（不確認就改系統設定）：你執行了危險系統操作（停用/刪除/殺進程/改設定）"
            "但沒有先向凱解釋每項操作會做什麼並等待確認。"
            "規則：停掉/刪除類操作 → 先解釋每項做什麼 → 等凱明確確認 → 再改。"
            "未經確認的破壞性操作可能導致系統不可用。"
        )

    if not warnings:
        print("{}")
        sys.exit(0)

    # 組合警告訊息
    severity = "WARNING" if len(warnings) == 1 else "CRITICAL"
    warning_text = f"[SELF-GUARD {severity}] 偵測到 {len(warnings)} 個行為壞模式：\n"
    for i, w in enumerate(warnings, 1):
        warning_text += f"\n{i}. {w}"

    if len(warnings) >= 2:
        warning_text += "\n\n多模式同時觸發，必須全部修正後再輸出。"
    else:
        warning_text += "\n\n請重新檢視你的回覆，修正後再輸出。"

    result = {"systemMessage": warning_text}
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
