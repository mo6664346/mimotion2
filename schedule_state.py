# -*- coding: utf-8 -*-
"""用 schedule_state.json 记录北京时间当天是否已经成功刷过步数。

同时负责「每天 20:00 ±30 分钟」的随机执行时刻：
目标时刻以日期为种子计算，稳定落在 19:30:00 ~ 20:29:59 之间。
同一天的所有触发算出的目标完全一致，因此不依赖额外的状态提交也能对齐。
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone

STATE_FILE = "schedule_state.json"
BEIJING = timezone(timedelta(hours=8))

# 目标窗口：每天 20:00 前后各 30 分钟，即 19:30 ~ 20:30
WINDOW_START_HOUR = 19
WINDOW_START_MINUTE = 30
WINDOW_SECONDS = 60 * 60


def now_beijing():
    return datetime.now(BEIJING)


def load_state():
    if not os.path.isfile(STATE_FILE):
        return {}
    with open(STATE_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def write_skip(skip):
    output = os.environ.get("GITHUB_OUTPUT")
    line = f"skip={'true' if skip else 'false'}\n"
    if not output:
        print(line.strip())
        return
    with open(output, "a", encoding="utf-8") as f:
        f.write(line)


def daily_target(day):
    """当天目标执行时刻，稳定落在 19:30:00 ~ 20:29:59。"""
    digest = hashlib.sha256(day.encode("utf-8")).hexdigest()
    offset = int(digest[:8], 16) % WINDOW_SECONDS
    base = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=BEIJING)
    return base + timedelta(
        hours=WINDOW_START_HOUR, minutes=WINDOW_START_MINUTE, seconds=offset
    )


def check():
    event = os.environ.get("EVENT_NAME", "")
    now = now_beijing()
    today = now.strftime("%Y-%m-%d")
    state = load_state()
    recorded = state.get("date") or ""
    target = daily_target(today)

    if event != "schedule":
        print(
            f"手动触发，直接执行。北京时间 {today} {now:%H:%M:%S}，"
            f"今天的目标时刻 {target:%H:%M:%S}"
        )
        write_skip(False)
        return

    if recorded == today:
        print(f"北京时间 {today} 已在 {state.get('executed_at')} 执行成功，跳过本次自动任务")
        write_skip(True)
        return

    if now < target:
        print(
            f"今天的目标执行时刻是 {target:%H:%M:%S}（20:00 ±30 分钟），"
            f"当前 {now:%H:%M:%S}，还没到点，跳过本次触发"
        )
        write_skip(True)
        return

    print(f"已到达今天的目标时刻 {target:%H:%M:%S}（当前 {now:%H:%M:%S}），开始执行")
    write_skip(False)


def mark():
    now = now_beijing()
    day = now.strftime("%Y-%m-%d")
    state = {
        "date": day,
        "executed_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "target": daily_target(day).strftime("%H:%M:%S"),
        "timezone": "Asia/Shanghai",
        "trigger": os.environ.get("EVENT_NAME", ""),
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"已记录今天的执行：{state['executed_at']}（目标 {state['target']}）")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "check"
    if command == "check":
        check()
    elif command == "mark":
        mark()
    else:
        print(f"未知命令：{command}")
        sys.exit(1)
