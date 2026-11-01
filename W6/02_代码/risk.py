# -*- coding: utf-8 -*-
"""
risk.py —— 读发现总表，算风险分，排修复优先级

用法：
    python risk.py                    # 读 ../01_笔记/发现总表.md 里的表格
    python risk.py --demo             # 用内置示例跑一遍，看看输出长什么样

评分口径（见 README）：
    风险分 = R × I × S        (0–27)
    优先级 = 风险分 / F        (F 越小越优先)
"""
import argparse
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
TABLE = os.path.normpath(os.path.join(HERE, "..", "01_笔记", "发现总表.md"))

DEMO = """| # | 编号 | 名称 | 来源 | R | I | S | F | 依据 |
|---|---|---|---|---|---|---|---|---|
| 1 | KB-01 | 知识库投毒 | W5 | 2 | 3 | 2 | 1 | 示例 |
| 2 | PI-01 | 间接注入劫持 | W2 | 2 | 3 | 3 | 1 | 示例 |
| 3 | SEC-01 | 密钥写在 prompt | W2 | 3 | 3 | 3 | 3 | 示例 |
| 4 | OUT-01 | 输出未转义 XSS | W2 | 2 | 2 | 2 | 2 | 示例 |
"""


def level(score):
    if score >= 18:
        return "严重"
    if score >= 12:
        return "高"
    if score >= 6:
        return "中"
    return "低"


def parse_rows(text):
    """从 Markdown 表格里抽出带 R/I/S/F 数字的行。"""
    rows = []
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 8:
            continue
        # 后四列必须是 0–3 的整数
        try:
            r, i, s, f = (int(cells[-5]), int(cells[-4]), int(cells[-3]), int(cells[-2]))
        except (ValueError, IndexError):
            continue
        if not all(0 <= x <= 3 for x in (r, i, s, f)) or f == 0:
            continue
        rows.append({"id": cells[1], "name": cells[2], "src": cells[3],
                     "R": r, "I": i, "S": s, "F": f, "why": cells[-1]})
    return rows


def report(rows):
    for x in rows:
        x["score"] = x["R"] * x["I"] * x["S"]
        # F 是「修复容易度」（3=一行改完），换算成成本后做分母
        x["cost"] = 4 - x["F"]
        x["prio"] = x["score"] / x["cost"]

    print("=" * 82)
    print("%-8s%-26s%-4s%-4s%-4s%-4s%-6s%-6s%-6s%s" %
          ("编号", "名称", "R", "I", "S", "F", "风险分", "等级", "成本", "优先级"))
    print("=" * 82)
    for x in sorted(rows, key=lambda y: -y["prio"]):
        print("%-8s%-26s%-4d%-4d%-4d%-4d%-6d%-6s%-6d%.1f" %
              (x["id"], x["name"][:24], x["R"], x["I"], x["S"], x["F"],
               x["score"], level(x["score"]), x["cost"], x["prio"]))
    print("=" * 82)

    # 修复批次
    ordered = sorted(rows, key=lambda y: -y["prio"])
    n = len(ordered)
    b1 = ordered[:max(1, round(n * 0.3))]
    b2 = ordered[len(b1):max(len(b1) + 1, round(n * 0.7))]
    b3 = ordered[len(b1) + len(b2):]

    print("\n修复路线图（按 风险分 ÷ 成本 排）")
    for name, batch in (("第一批（本周）", b1), ("第二批（本月）", b2), ("第三批（本季）", b3)):
        if not batch:
            continue
        print("\n%s：" % name)
        for x in batch:
            print("  - %-8s %-24s 风险 %d（%s）　成本 %d" %
                  (x["id"], x["name"][:22], x["score"], level(x["score"]), x["cost"]))

    # 矩阵
    print("\n风险矩阵（影响 × 稳定性，取最高可达性）")
    print("%-6s%-10s%-10s%-10s" % ("", "S=1", "S=2", "S=3"))
    for i in (3, 2, 1):
        line = "%-6s" % ("I=%d" % i)
        for s in (1, 2, 3):
            ids = [x["id"] for x in rows if x["I"] == i and x["S"] == s]
            line += "%-10s" % (",".join(ids)[:9] if ids else "—")
        print(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--table", default=TABLE)
    args = ap.parse_args()

    if args.demo:
        text = DEMO
    else:
        if not os.path.exists(args.table):
            raise SystemExit("找不到 %s" % args.table)
        text = open(args.table, encoding="utf-8").read()

    rows = parse_rows(text)
    if not rows:
        raise SystemExit("表里没有找到带 R/I/S/F 的行，检查格式")
    print("解析到 %d 条发现\n" % len(rows))
    report(rows)


if __name__ == "__main__":
    main()
