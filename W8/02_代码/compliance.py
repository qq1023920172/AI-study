# -*- coding: utf-8 -*-
"""
compliance.py —— 读条款清单，算合规完成度，出差距表

用法：
    python compliance.py                    # 读条款清单.csv
    python compliance.py --csv 我的清单.csv

状态取值（不区分大小写）：
    满足 / 部分 / 不满足 / 不适用 / 未填
"""
import argparse
import csv
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "条款清单.csv")
OUT_DIR = os.path.normpath(os.path.join(HERE, "..", "03_结果"))
MD_PATH = os.path.join(OUT_DIR, "合规差距表.md")

STATUS = ["满足", "部分", "不满足", "不适用", "未填"]


def norm(s):
    s = (s or "").strip()
    for k in ("满足", "部分满足", "部分", "不满足", "不符合", "不适用", "未填"):
        if s.startswith(k):
            if k == "部分满足":
                return "部分"
            if k == "不符合":
                return "不满足"
            return k
    return "未填"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=CSV_PATH)
    args = ap.parse_args()

    if not os.path.exists(args.csv):
        raise SystemExit("找不到 %s" % args.csv)

    rows = list(csv.DictReader(open(args.csv, encoding="utf-8-sig")))
    for r in rows:
        r["状态"] = norm(r.get("状态", ""))

    # 按类别统计
    cat = defaultdict(lambda: defaultdict(int))
    for r in rows:
        cat[r["类别"]][r["状态"]] += 1
        cat[r["类别"]]["总数"] += 1

    total = len(rows)
    done = sum(1 for r in rows if r["状态"] == "满足")
    part = sum(1 for r in rows if r["状态"] == "部分")
    miss = sum(1 for r in rows if r["状态"] == "不满足")
    na = sum(1 for r in rows if r["状态"] == "不适用")
    blank = sum(1 for r in rows if r["状态"] == "未填")
    effective = total - na

    print("=" * 70)
    print("条款 %d 条（不适用 %d，有效 %d）" % (total, na, effective))
    print("  满足 %2d　部分 %2d　不满足 %2d　未填 %2d" % (done, part, miss, blank))
    if effective:
        print("  完成度（满足 / 有效）：%.0f%%" % (done * 100 / effective))
        print("  含部分满足的加权完成度：%.0f%%" %
              ((done + part * 0.5) * 100 / effective))
    print("=" * 70)

    print("\n按类别：")
    print("%-12s%-6s%-6s%-6s%-6s%-6s%s" % ("类别", "总数", "满足", "部分", "不满足", "未填", "完成度"))
    for c in sorted(cat):
        d = cat[c]
        eff = d["总数"] - d.get("不适用", 0)
        rate = (d["满足"] * 100 / eff) if eff else 0
        print("%-12s%-6d%-6d%-6d%-6d%-6d%.0f%%" %
              (c, d["总数"], d["满足"], d["部分"], d["不满足"], d["未填"], rate))

    # 出差距表
    lines = ["# 合规差距表\n",
             "> 条款 %d 条，有效 %d 条；满足 %d，部分 %d，不满足 %d。\n"
             % (total, effective, done, part, miss)]

    lines.append("## 一、未满足项（按优先级排）\n")
    lines.append("| 编号 | 类别 | 要求 | 状态 | 对应发现 | 证据位置 |")
    lines.append("|---|---|---|---|---|---|")
    for r in rows:
        if r["状态"] in ("不满足", "部分", "未填"):
            lines.append("| %s | %s | %s | %s | %s | %s |" % (
                r["编号"], r["类别"], r["要求（按主题归纳）"],
                r["状态"], r.get("对应发现", "") or "—", r.get("证据位置", "") or "—"))

    lines.append("\n## 二、已满足项\n")
    lines.append("| 编号 | 类别 | 要求 | 证据位置 |")
    lines.append("|---|---|---|---|")
    for r in rows:
        if r["状态"] == "满足":
            lines.append("| %s | %s | %s | %s |" % (
                r["编号"], r["类别"], r["要求（按主题归纳）"], r.get("证据位置", "")))

    lines.append("\n## 三、走查记录\n")
    lines.append("<!-- 每补上一条，写下：补了什么、谁补的、证据在哪 -->")
    lines.append("- ")
    lines.append("")
    lines.append("> 状态口径：「部分」= 有措施但缺证据，或措施不完整。合规上等同未满足。")

    os.makedirs(OUT_DIR, exist_ok=True)
    open(MD_PATH, "w", encoding="utf-8").write("\n".join(lines))
    print("\n已写入 %s" % MD_PATH)


if __name__ == "__main__":
    main()
