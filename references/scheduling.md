# 定期运行 · scheduling.md

目标：每周五按用户设定时间自动生成并推送周报。

## 关键认知

写进 `state.py` 的 `schedule` **只是记录意图，不会自动触发**。要真正开启定期运行，agent
**必须实际调用宿主的 automation 工具**创建循环任务，并回读确认「任务已建 + 下次触发时间」。

若宿主无法唤起 agent 做推理（纯 cron 跑不了推理），**如实告知**「未能自动拉起，需要你到时手动
触发一次」，不得默认已生效。

## 开启步骤

1. 确认调度参数已存：`python3 scripts/state.py show` 看 `schedule`（默认周五 = weekday 4）。
   如需改：`python3 scripts/state.py set-schedule --report-time 17:00 --weekday 4 --timezone Asia/Shanghai`。
2. 调用宿主 automation 工具，创建「每周五 <report_time> Asia/Shanghai」的循环任务，
   任务内容 = 运行本 skill 的默认周报流程。
3. 回读宿主返回的下次触发时间，向用户复述确认。
4. 若宿主不支持唤起推理：明确告知需手动触发，并给出手动触发的一句话指令。

## 每周跑（循环任务体）

窗口用「上次成功 → 本次」，等价于「上周五同点 → 本周五」：

1. `python3 scripts/state.py window --at "<now RFC3339>"` 取窗口。
2. 按 `roster.py show` 逐人采集（见 collection.md）。
3. 用 `state.py seen` 过滤已上报过的内容，避免跨周重复。
4. 按 `output-contract.md` 当前风格成稿。
5. `im +messages-send --user-id <self ou_...> --markdown` 推送给用户本人。
6. 发送成功后 `state.py mark-success --at "<window.end>"` 落盘指纹与成功时间。

## 首次 vs 之后

- 首次：需引导 roster（见 SKILL.md），窗口是 baseline 7 天。
- 之后：roster 已存，只重复上面的每周跑；roster 一般不重算，仅在 leader 变动时更新。
