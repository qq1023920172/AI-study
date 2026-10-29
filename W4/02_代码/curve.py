# -*- coding: utf-8 -*-
"""
curve.py —— 算 ASR@k，画「迭代轮数—累计成功率」曲线

用法：
    python curve.py

输出：
    03_结果/curve.md   表格 + 柱状图 + 和 W3 静态结果的对比
    终端也会打印
"""
import csv
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.normpath(os.path.join(HERE, "..", "03_结果"))
CSV_PATH = os.path.join(OUT_DIR, "pair_results.csv")
MD_PATH = os.path.join(OUT_DIR, "curve.md")

W3_STATIC_ASR = 0.384      # W3 版本4 的静态 ASR，用来画对照线


def load(path=None):
    path = path or CSV_PATH
    if not os.path.exists(path):
        raise SystemExit("找不到 %s，先跑 attacker_node.py" % path)
    rows = [r for r in csv.DictReader(open(path, encoding="utf-8"))
            if r["iteration"] not in ("-1", "")]
    seeds = defaultdict(list)
    for r in rows:
        seeds[r["seed_id"]].append(r)
    return seeds


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=None,
                    help="指定结果文件，如 ../03_结果/pair_results_enc.csv")
    args = ap.parse_args()

    seeds = load(args.csv)
    if not seeds:
        raise SystemExit("没有有效数据")

    total = len(seeds)
    max_iter = max(max(int(r["iteration"]) for r in rs) for rs in seeds.values())
    has_zero = any(0 in [int(r["iteration"]) for r in rs] for rs in seeds.values())
    min_k = 0 if has_zero else 1

    # 每条种子的"首次成功轮次"，没成功记 None
    first_hit = {}
    for sid, rs in seeds.items():
        hit = [int(r["iteration"]) for r in rs if r["success"] == "1"]
        first_hit[sid] = min(hit) if hit else None

    lines = ["# W4 自适应攻击曲线\n",
             "> 种子 %d 条，最多 %d 轮\n" % (total, max_iter),
             "## ASR@k（k 轮之内至少成功一次的比例）\n",
             "| 轮数 k | 成功种子数 | ASR@k |",
             "|---|---|---|"]

    print("%-8s%-12s%-10s" % ("轮数", "成功数", "ASR@k"))
    for k in range(min_k, max_iter + 1):
        ok = sum(1 for v in first_hit.values() if v is not None and v <= k)
        r = ok / total
        label = "%d" % k if k > 0 else "0（原样种子）"
        print("%-8s%-12d%-10.0f%%" % (label, ok, r * 100))
        lines.append("| %s | %d | %.0f%% |" % (label, ok, r * 100))

    final = sum(1 for v in first_hit.values() if v is not None) / total
    avg_iter = [v for v in first_hit.values() if v is not None]
    avg = sum(avg_iter) / len(avg_iter) if avg_iter else 0
    base = sum(1 for v in first_hit.values() if v == 0) / total if has_zero else None

    print("\n最终 ASR：%.0f%%（%d/%d）" % (final * 100, sum(1 for v in first_hit.values() if v is not None), total))
    if base is not None:
        print("静态基线 ASR@0（原样种子）：%.0f%%" % (base * 100))
        print("自适应增益：%+.0f 个百分点" % ((final - base) * 100))
    else:
        print("注意：没有第 0 轮数据，无法给出静态基线。建议加 iteration 0 重跑。")
    print("成功者的平均突破轮次：%.1f" % avg)

    # 柱状图
    chart = ["", "## 曲线（每格 ≈ 5%）", "", "```"]
    for k in range(min_k, max_iter + 1):
        ok = sum(1 for v in first_hit.values() if v is not None and v <= k)
        bar = "█" * int(round(ok / total * 20))
        tag = "k=%-2d " % k if k > 0 else "k=0  "
        chart.append("%s%-20s %3.0f%%" % (tag, bar, ok / total * 100))
    chart.append("```")

    lines += chart
    lines += ["", "## 读法", "",
              "- **k=0** 是原样种子的成功率，也就是真正的「不做自适应」基线",
              "- **k=1** 是改写一次之后的结果——注意改写可能先把载荷降级",
              "- 曲线的**拐点**在哪一轮：走平之后再加预算就是浪费",
              "- 平均突破轮次越小，说明 attacker 越会改；一直不降说明它在原地打转",
              ""]

    md = "\n".join(str(x) for x in lines)
    open(MD_PATH, "w", encoding="utf-8").write(md)
    print("\n已写入 %s" % MD_PATH)


if __name__ == "__main__":
    main()
