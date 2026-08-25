---
name: boss-reports-to-me
description: |
  「老板向我汇报」——把组织架构上你的各层直属 leader，反过来向你汇报本周动态。每周五（可调）沿 roster 收集每位 leader 在本周内、你有权限可见的会议智能纪要/妙记、消息发言、撰写文档（按信息密度排序），按人名分段结构化成含「总结·观点·原文·下一步」的周报，通过飞书消息推送给你本人。用户说「老板向我汇报」「让我的老板给我汇报」「本周我领导在忙什么/关注什么」「上级动态周报」「leader 周报」「boss reports to me」，或要设置/查看/停用这类每周汇报时使用。仅限本人自愿自读、只用本人已有权限内容，不做他人画像/绩效判断，不用于监控。
---

# 老板向我汇报 (Boss Reports To Me)

## 这个 skill 做什么

沿组织架构收集你的各层 leader（直属上级 + 你选择覆盖的更上层）在本周内**你有权限可见**的
飞书资产（会议纪要 / 消息发言 / 文档，按信息密度排序），按人名分段汇总成周报，推送给你本人。默认每周五运行。

**边界（重要）**：只用当前用户本人已有权限能看到的内容（`--as user` 天然如此）；只做「本周动态摘要」，
不给 leader 建人物档案、不做绩效/能力判断、不用于监控。采集到的原文**不落盘、不进记忆**。

## 环境前提

- company 飞书账号（`--as user`）。运行前 `lark-cli auth status --json --verify` 确认 identity=user、
  租户正确。公私飞书严格隔离，不混 profile / token。
- 私有状态目录 `~/.codex/boss-reports-to-me/`（0600）：`roster.json`（leader 名单）+ `state.json`
  （调度 + 去重指纹）。可用环境变量 `BOSS_REPORTS_ROSTER_PATH` / `BOSS_REPORTS_STATE_PATH` 覆盖。

## 流程决策

- **首次 / roster 为空** → 走「A. 首次安装」建 roster 与调度，再跑一次周报。
- **roster 已存，用户要周报** → 走「B. 每周跑」。
- **用户要改风格 / 时间 / 增删 leader** → 走「C. 调整」。
- **用户要开启定期运行** → 读 `references/scheduling.md`。

---

## A. 首次安装

1. **身份门**：`lark-cli auth status --json --verify`，确认 identity=user、租户正确。

2. **建 roster —— 默认手动，永远可用**（不依赖任何补授权）：
   - 直接问用户两件事：①「你的直属上级是谁？」②「除直属外，还想让哪些上层 leader 定期向你汇报？」
     （可给层级提示：+2 是老板的老板，以此类推，最多 +4。）
   - 逐个把姓名/邮箱解析成 open_id：
     ```bash
     lark-cli contact +search-user --as user --query "姓名或邮箱" --format json
     ```
     多个同名时用 `has_chatted: true` / `p2p_chat_id` / `department` 辅助确认是本人，**必须让用户核对**再写入。
   - 写入 roster（level 用 `直属上级` 或 `+2`/`+3`/`+4`）：
     ```bash
     python3 scripts/roster.py add --name "张三" --open-id ou_xxx --level 直属上级
     python3 scripts/roster.py add --name "李四" --open-id ou_yyy --level +2
     ```

3. **（可选）自动上级链**：若用户愿意补授权，可自动沿 `leader_open_id` 向上取 4 层，省去手动报名单：
   ```bash
   python3 scripts/leader_chain.py --levels 4
   ```
   - 若输出 `needs_scope: true`：说明缺 `contact:contact.base:readonly`。按提示引导一次性授权
     （`lark-cli auth login --scope "contact:contact.base:readonly" --no-wait --json` → 把 verification_url
     原样给用户、结束本轮 → 用户确认后 `lark-cli auth login --device-code <device_code>`），再重跑。
   - 授权是一次性的，之后自动跑不再需要。**拿不到授权不阻断**——静默留在手动 roster 模式即可。
   - 拿到 chain 后把每位 leader 念给用户核对，确认无误再用 `roster.py add` 写入。

4. **初始化调度**（默认周五 17:00、幕僚四段风格）：
   ```bash
   python3 scripts/state.py init --report-time 17:00 --timezone Asia/Shanghai --weekday 4 --style chief
   ```

5. 接着跑一次「B. 每周跑」，把首份周报**先发给用户确认格式**，再谈定期运行。

---

## B. 每周跑

1. **取窗口**（「上次成功 → 现在」，等价「上周五 → 本周五」）：
   ```bash
   python3 scripts/state.py window --at "$(date -Iseconds)"
   ```
2. **取 roster**：`python3 scripts/roster.py show`。
3. **逐人采集**（按信息密度，纪要优先）：对每位 leader 收集
   **① 会议纪要/妙记（主口径）→ ② 消息发言 → ③ 文档（弱信号，有则补充）**。
   命令、字段名、解析陷阱见 **`references/collection.md`**。三个高频坑：
   - 纪要用 `--participant-ids`（不是 `--owner-ids`，owner 几乎全空），结果在 `data.items`；
   - IM 结果在 `data.messages`，`content` 已是纯文本，**不要二次 `json.loads`**；
   - 文档对上级链常无产出，别为凑「三类」强撑。空结果是合法结果。
4. **去重**：对候选内容算指纹并过滤已上报过的：
   ```bash
   printf '%s' "$content" | python3 scripts/state.py fingerprint --source minute   # im / doc
   cat all_fps.txt | python3 scripts/state.py seen   # 只回未上报过的
   ```
5. **成稿**：按 **`references/output-contract.md`** 当前风格（默认幕僚四段：总结·观点·原文·下一步），
   原文按密度排序（纪要→消息→文档）。高交集 leader 独立成段；证据 < 3 条且来源单一的更上层
   并入「上层零星信号」合并段。顶部一句总判断，每条带可点击来源+时间。相关性三重过滤。
6. **发送**：取本人 open_id（`lark-cli contact +get-user --as user`），推送：
   ```bash
   lark-cli im +messages-send --as user --user-id ou_SELF --markdown "<周报>"
   ```
   富卡片走 lark-im 的强制卡片工作流，不手写卡片 JSON。
7. **落盘**：发送成功后记录成功时间与指纹（防跨周重复）：
   ```bash
   cat all_fps.txt | python3 scripts/state.py mark-success --at "<window.end RFC3339>"
   ```

---

## C. 调整

- 改风格：`python3 scripts/state.py set-schedule --style <chief|sair|humor>`（见 output-contract.md 三种风格）。
- 改时间/周几：`python3 scripts/state.py set-schedule --report-time 09:30 --weekday 0`（0=周一…4=周五）。
- 增删 leader：`python3 scripts/roster.py add ...` / `remove --open-id ou_xxx` / `show`。
- 开启/确认定期运行：见 **`references/scheduling.md`**（调宿主 automation 建循环任务并回读，
  纯 cron 唤不起推理时如实告知需手动触发）。

---

## 隐私与安全纪律

- 全程 `--as user`；混入 bot 身份会 `99992361 open_id cross app`。
- 只用本人有权限可见内容；无权限就在周报里标注（如「无纪要查看权限」），不臆造、不外推。
- 不把 AI 会议摘要当事实，缺一手佐证时停止下钻。
- state 只存调度参数 + `source:sha256` 指纹，绝不存原文/token/凭证；roster 只存姓名/open_id/层级标签。
- 这是「向上」读人，比读同级更敏感：抽象成行为/主题，不做人物画像、不做绩效判断、不用于监控。
