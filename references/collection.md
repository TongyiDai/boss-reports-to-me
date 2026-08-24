# 采集参考 · collection.md

对 roster 里每位 leader，在周窗口内采集三类**你有权限可见**的飞书资产。全程 `--as user`：
搜索结果天然只返回当前用户有权限看到的内容，这既是功能也是隐私边界——不要试图绕过。

窗口来自 `state.py window`，形如 `{"start": "...+08:00", "end": "...+08:00"}`。

## 目录
1. 发言（IM 消息）
2. 文档（drive）
3. 会议纪要 / 妙记（minutes + vc）
4. 去重与指纹
5. 解析陷阱清单

---

## 1. 发言（IM 消息）

按 sender 过滤 leader 的发言，**`--query` 必须留空**——放"总结/发言/看看"之类词会过度约束、漏消息。靠 sender + 时间召回。

```bash
lark-cli im +messages-search --as user \
  --query "" --sender ou_LEADER \
  --start "2026-08-18T00:00:00+08:00" --end "2026-08-24T23:59:59+08:00" \
  --page-size 50 --page-all --format json --no-reactions
```

- 必须分页取全（`--page-all`），一页不够做周报。
- 每条保留 `chat_name`、`sender.name`、`create_time`、`message_id` 作为证据。
- 只会命中你和该 leader 共同所在的群/私聊——这是正确的权限边界。
- 需要 scope：`search:message`（已具备）。

## 2. 文档（drive）

按 owner/creator 过滤 leader 本周新建或改动的文档：

```bash
# 本周新建（窗口内）
lark-cli drive +search --as user --creator-ids ou_LEADER \
  --doc-types doc,docx,sheet,bitable,wiki,file --sort create_time \
  --created-since 2026-08-18 --created-until 2026-08-24 \
  --page-size 20 --format json
```

- 结果字段在 `data.results[].result_meta`（`.title` / `.token` / `.create_time_iso` / `.owner_name`），
  顶层字段常为 null；`data.total` 忽略日期过滤，**必须翻页后在内存里按 `create_time` 精确回裁到窗口**。
- 日期过滤按自然日召回，边界要自己再收紧。
- 剔除导入批量噪声：同一天大量、标题统一前缀的多为导入批次，不是真实撰写。
- 需要 scope：`search:docs`（已具备）。可选跑第二遍 `--sort edit_time` 召回"本周改动的旧文档"。

## 3. 会议纪要 / 妙记（minutes + vc）

```bash
# 妙记：该 leader owner 或参与的
lark-cli minutes +search --as user \
  --owner-ids ou_LEADER \
  --start 2026-08-18 --end 2026-08-24 --format json
# 也可加 --participant-ids ou_LEADER

# 会议记录：该 leader 主持或参与
lark-cli vc +search --as user \
  --organizer-ids ou_LEADER \
  --start "2026-08-18T00:00:00+08:00" --end 2026-08-24 --format json
# 也可加 --participant-ids ou_LEADER
```

- `minutes +search` 的 `display_info` 是一整块 HTML 转义富文本（无独立标题/开始时间）：取首行、去标签；开始时间从 `meta_data.description` 里取。
- 从 `vc +search` 拿到 top 会议后，用 `vc +detail` 找到纪要入口，按 `note_id` / `minute_token` 路由到 `lark-note` / `lark-minutes` 取正文。
- 证据语言纪律：没有纪要查看权限就明确标注（如"未参会 / 无纪要查看权限"），**不要把 AI 会议摘要当作事实**，缺一手佐证时停止下钻。
- 需要 scope：`minutes:minutes.search:read`、`vc:meeting.search:read`、`vc:note:read`（已具备）。

## 4. 去重与指纹

跨周不重复上报同一条内容：对每条候选算指纹，只保留新的。

```bash
# 对一条消息内容算指纹（source 用 im/doc/minute）
printf '%s' "$content" | python3 scripts/state.py fingerprint --source im

# 把本周所有候选指纹喂给 seen，只回未上报过的
cat fingerprints.txt | python3 scripts/state.py seen

# 周报成功发送后落盘
cat fingerprints.txt | python3 scripts/state.py mark-success --at "<end-of-window RFC3339>"
```

指纹用内容本身（消息文本 / 文档 token+标题 / minute_token）作为输入，state 只存 `source:sha256`，不存原文。

## 5. 解析陷阱清单

- `--as user` 全程一致；混入 bot 身份会因 open_id 跨应用报 `99992361 open_id cross app`。
- `im +messages-search` 分页不取全 = 周报不完整。
- `drive +search` 认 `result_meta`，别读顶层；`data.total` 不可信。
- `minutes +search` 的 `display_info` 是转义 HTML，需去标签取首行。
- 空结果是合法结果：某 leader 本周无可见动态，就在周报里如实标注"本周无可见公开动态"，不臆造。
