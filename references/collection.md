# 采集参考 · collection.md

对 roster 里每位 leader，在周窗口内采集三类**你有权限可见**的飞书资产。全程 `--as user`：
搜索结果天然只返回当前用户有权限看到的内容，这既是功能也是隐私边界——不要试图绕过。

窗口来自 `state.py window`，形如 `{"start": "...+08:00", "end": "...+08:00"}`。

## 采集与呈现优先级（重要）

按**信息密度**排序，纪要最高、文档最低：

1. **会议纪要 / 智能纪要 / 逐字记录** —— 结论密度最高，一场会顶几十条零散消息。
2. **消息发言** —— 及时、有态度，但零散、需要聚合。
3. **文档** —— 对「向上级链」场景**基本失效**（见下），有则锦上添花，无则不必强凑。

周报成稿也按这个顺序：先讲会上说了什么，再讲群里说了什么，文档作为补充。

## 目录
1. 会议纪要 / 妙记（minutes + vc）— 主口径
2. 发言（IM 消息）
3. 文档（drive）— 弱信号
4. 去重与指纹
5. 解析陷阱清单

---

## 1. 会议纪要 / 妙记（minutes + vc）— 主口径

**关键口径修正：leader 极少是妙记 owner。** 纪要通常挂在会议组织者或秘书名下，而不是你的 leader。
因此**必须以 `--participant-ids`（参与人）为主口径**，`--owner-ids`（owner）几乎全空。按 owner 跑，纪要这一类会整体丢掉。

```bash
# 主口径：该 leader 作为参与人的妙记（这才有货）
lark-cli minutes +search --as user \
  --participant-ids ou_LEADER \
  --start 2026-08-18 --end 2026-08-24 --format json

# 会议记录：该 leader 参与的会议（同样以 participant 为主）
lark-cli vc +search --as user \
  --participant-ids ou_LEADER \
  --start "2026-08-18T00:00:00+08:00" --end 2026-08-24 --format json
# --organizer-ids 只作补充，多数 leader 不亲自当组织者
```

- 结果在 **`data.items`**（不是 `results`/`messages`），每项含 `token` / `display_info` / `meta_data`。
- `display_info` 是一整块 HTML 转义富文本（无独立标题/开始时间）：取首行、去标签；开始时间从 `meta_data.description` 里取。
- 从 `vc +search` 拿到 top 会议后，用 `vc +detail` 找到纪要入口，按 `note_id` / `minute_token` 路由到 `lark-note` / `lark-minutes` 取正文。
- 证据语言纪律：没有纪要查看权限就明确标注（如"未参会 / 无纪要查看权限"），**不要把 AI 会议摘要当作事实**，缺一手佐证时停止下钻。
- 需要 scope：`minutes:minutes.search:read`、`vc:meeting.search:read`、`vc:note:read`（已具备）。

## 2. 发言（IM 消息）

按 sender 过滤 leader 的发言，**`--query` 必须留空**——放"总结/发言/看看"之类词会过度约束、漏消息。靠 sender + 时间召回。

```bash
lark-cli im +messages-search --as user \
  --query "" --sender ou_LEADER \
  --start "2026-08-18T00:00:00+08:00" --end "2026-08-24T23:59:59+08:00" \
  --page-size 50 --page-all --format json --no-reactions
```

- 结果在 **`data.messages`**（不是 `data.items`）。分页取全（`--page-all`），一页不够做周报。
- **`content` 已是纯文本字符串，不要再 `json.loads`。** 直接用即可：
  - `text` → 纯文本；`post` → 文本含 `![Image](img_...)` 标记；`sticker` → `[Sticker]`；
  - `image` → `[Image: img_...]`；`file` → `<file key="..." name="xxx.pptx"/>`；`share_calendar_event` → `<calendar_share .../>`。
  - 按文档旧写法做二次 json 解析，会把 194 条全变成 `[unparsed]`——这是最容易踩的坑。
- 每条保留 `chat_name`、`sender.name`、`create_time`、`message_id` 作为证据。
- 只会命中你和该 leader 共同所在的群/私聊——这是正确的权限边界，也意味着**共同群越少、可见面越小**（见文末密度判断）。
- 需要 scope：`search:message`（已具备）。

## 3. 文档（drive）— 弱信号

```bash
lark-cli drive +search --as user --creator-ids ou_LEADER \
  --doc-types doc,docx,sheet,bitable,wiki,file --sort create_time \
  --created-since 2026-08-18 --created-until 2026-08-24 \
  --page-size 20 --format json
```

- **对上级链场景基本失效**：你的 leader 层不亲自建文档，产出多挂在他人或机器人名下（如双周会文档由机器人代建）。四人合计常常只有个位数、且非本人所写。
- 因此文档只作**补充信号**：有真实本人撰写的就带上，没有就跳过，**不要为凑「三类资产」而强行呈现**。
- 结果字段在 `data.results[].result_meta`（`.title` / `.token` / `.create_time_iso` / `.owner_name`），顶层字段常为 null；`data.total` 忽略日期过滤，**必须翻页后在内存里按 `create_time` 精确回裁到窗口**。
- 剔除导入批量噪声与机器人代建：同一天大量、统一前缀、owner 为机器人的，不算 leader 的真实产出。
- 需要 scope：`search:docs`（已具备）。

## 4. 去重与指纹

跨周不重复上报同一条内容：对每条候选算指纹，只保留新的。

```bash
# 对一条内容算指纹（source 用 minute/im/doc）
printf '%s' "$content" | python3 scripts/state.py fingerprint --source minute

# 把本周所有候选指纹喂给 seen，只回未上报过的
cat fingerprints.txt | python3 scripts/state.py seen

# 周报成功发送后落盘
cat fingerprints.txt | python3 scripts/state.py mark-success --at "<end-of-window RFC3339>"
```

指纹用内容本身（minute_token / 消息文本 / 文档 token+标题）作为输入，state 只存 `source:sha256`，不存原文。

## 5. 解析陷阱清单

- `--as user` 全程一致；混入 bot 身份会因 open_id 跨应用报 `99992361 open_id cross app`。
- **纪要按 `--participant-ids` 而非 `--owner-ids`**：owner 几乎全空，参与人才有货。
- **`minutes +search` 结果在 `data.items`**；`im +messages-search` 结果在 `data.messages`。别记混。
- **IM `content` 已是纯文本，不要二次 `json.loads`**，否则整批变 `[unparsed]`。
- `drive +search` 认 `result_meta`，别读顶层；`data.total` 不可信；上级链场景文档普遍无产出。
- 空结果是合法结果：某 leader 本周无可见动态，就在周报里如实标注"本周无可见公开动态"，不臆造。

## 关于信号密度（供成稿判断）

**越往上，信号越接近噪声——不是 leader 不活跃，是你和他们的共同群太少，权限边界决定了可见面。**

- 与你业务交集大的上层（通常是 +1，或个别深度协作的 +2）：信号密度高，值得独立成段、完整幕僚四段。
- 交集小的更上层（+2/+3/+4）：可能全周只有几条、且集中在同一场沟通。这时**不要硬凑周报**：
  - 定期跑时，这些层可**降频**（如每月一次）或**合并成一段「上层零星信号」**，一句话带过，附来源即可。
  - 若某层全周 0 条可见内容，如实标注，不臆造、不用文档凑数。
- 成稿判断规则：单个 leader 本周可见证据 < 3 条且来源单一时，降级为「零星信号」并入合并段，不单独成段。
