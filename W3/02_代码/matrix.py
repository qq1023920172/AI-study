# -*- coding: utf-8 -*-
"""
matrix.py —— 把 results.csv 变成能看的成功率矩阵

用法：
    python matrix.py

输出：
    03_结果/matrix.md   （三张表：类别×模型 / 强度×模型 / 载荷排行）
    终端也会打印一份
"""
import os
import csv
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.normpath(os.path.join(HERE, "..", "03_结果"))
CSV_PATH = os.path.join(OUT_DIR, "results.csv")
MD_PATH = os.path.join(OUT_DIR, "matrix.md")


def load():
    if not os.path.exists(CSV_PATH):
        raise SystemExit(f"找不到 {CSV_PATH}，先跑 runner.py")
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def rate(rows):
    if not rows:
        return 0.0, 0
    ok = sum(int(r["success"]) for r in rows)
    return ok / len(rows), len(rows)


def table(rows, row_key, col_key="model"):
    row_vals = sorted({r[row_key] for r in rows})
    col_vals = sorted({r[col_key] for r in rows})
    cell = defaultdict(list)
    for r in rows:
        cell[(r[row_key], r[col_key])].append(r)

    lines = []
    head = "| " + row_key + " | " + " | ".join(col_vals) + " | 合计 |"
    lines.append(head)
    lines.append("|" + "---|" * (len(col_vals) + 2))

    for rv in row_vals:
        cells = []
        for cv in col_vals:
            p, n = rate(cell.get((rv, cv), []))
            cells.append(f"{p*100:.0f}% ({int(round(p*n))}/{n})" if n else "—")
        p_all, n_all = rate([r for r in rows if r[row_key] == rv])
        lines.append(f"| **{rv}** | " + " | ".join(cells) + f" | {p_all*100:.0f}% |")

    return "\n".join(lines)


def top_payloads(rows, k=10):
    agg = defaultdict(list)
    for r in rows:
        agg[r["payload_id"]].append(r)
    ranked = sorted(agg.items(), key=lambda kv: -rate(kv[1])[0])
    lines = ["| 载荷 | 类别 | 成功率 | 次数 |", "|---|---|---|---|"]
    for pid, rs in ranked[:k]:
        p, n = rate(rs)
        lines.append(f"| `{pid}` | {rs[0]['category']} | {p*100:.0f}% | {n} |")
    return "\n".join(lines)


def main():
    rows = load()
    models = sorted({r["model"] for r in rows})
    total = len(rows)
    overall, _ = rate(rows)

    parts = [
        "# W3 攻击成功率矩阵\n",
        f"> 生成时间：{rows[-1]['ts']}　|　样本量：{total} 次调用　|　模型：{', '.join(models)}\n",
        f"**总体攻击成功率（ASR）：{overall*100:.0f}%**\n",
        "> 注意：这里的「成功」由 `judge.py` 自动判定，存在漏报与误判。"
        "写报告时必须人工抽检 10%，并注明判定偏差。\n",
        "\n## 一、按类别 × 模型\n",
        table(rows, "category"),
        "\n## 二、按话术强度 × 模型\n",
        table(rows, "modality"),
        "\n## 三、成功率最高的载荷\n",
        top_payloads(rows),
        "\n## 四、怎么读这张表\n",
        "- **类别之间**的差异，说明哪类手法更有效 → 决定以后优先测什么",
        "- **模型之间**的差异，就是跨模型迁移率 → 决定红队能否「打小的、推大的」",
        "- **强度之间**的差异，验证 W1 的结论：许可级接近 0，义务级接近 100",
        "- 样本量 < 15 的格子不要下结论，只能当线索",
    ]

    md = "\n".join(parts)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(MD_PATH, "w", encoding="utf-8") as f:
        f.write(md)

    print(md)
    print(f"\n已写入 {MD_PATH}")


if __name__ == "__main__":
    main()
