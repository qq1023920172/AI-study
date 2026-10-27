# -*- coding: utf-8 -*-
"""
noise_check.py —— 同一批载荷跑两次，差异到底是信号还是噪声？

用法：
    python noise_check.py 版本1 版本2

输出：
    每个格子的成功率 + 95% 置信区间（Wilson）
    两版之间区间是否重叠 —— 重叠就说明「差异不显著」

为什么需要它：
    n=4 的时候，25% 和 75% 的差别完全可能是随机波动。
    不做这一步，你会把噪声当成"我的改动生效了"。
"""
import csv
import math
import os
import sys
from collections import defaultdict

BASE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "03_结果"))


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - m) / d, (c + m) / d


def load(version):
    path = os.path.join(BASE, version, "results.csv")
    if not os.path.exists(path):
        raise SystemExit("找不到 %s" % path)
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def agg(rows, keys):
    d = defaultdict(lambda: [0, 0])
    for r in rows:
        k = tuple(r[x] for x in keys)
        d[k][0] += int(r["success"])
        d[k][1] += 1
    return d


def main():
    v1 = sys.argv[1] if len(sys.argv) > 1 else "版本1"
    v2 = sys.argv[2] if len(sys.argv) > 2 else "版本2"

    r1, r2 = load(v1), load(v2)
    a1, a2 = agg(r1, ("category", "model")), agg(r2, ("category", "model"))

    print("行数：%s=%d　%s=%d" % (v1, len(r1), v2, len(r2)))
    print()
    print("%-10s%-16s%-20s%-20s%s" % ("类别", "模型", v1, v2, "区间重叠"))
    overlap = 0
    for k in sorted(a1):
        k1, n1 = a1[k]
        k2, n2 = a2.get(k, (0, 0))
        lo1, hi1 = wilson(k1, n1)
        lo2, hi2 = wilson(k2, n2)
        ov = not (hi1 < lo2 or hi2 < lo1)
        overlap += ov
        print("%-10s%-16s%-20s%-20s%s" % (
            k[0], k[1],
            "%d/%d [%.0f%%-%.0f%%]" % (k1, n1, lo1 * 100, hi1 * 100),
            "%d/%d [%.0f%%-%.0f%%]" % (k2, n2, lo2 * 100, hi2 * 100),
            "是" if ov else "否"))

    print("\n区间重叠的格子：%d/%d" % (overlap, len(a1)))
    if overlap == len(a1):
        print("→ 两版之间没有一个格子的差异达到统计显著。")
        print("  如果你在这两版之间改过代码，那个改动很可能没有真正生效。")

    deltas = []
    for k in a1:
        p1 = a1[k][0] / a1[k][1]
        k2, n2 = a2.get(k, (0, 1))
        p2 = k2 / n2 if n2 else 0
        deltas.append((abs(p1 - p2), k, p1, p2))
    deltas.sort(reverse=True)
    print("\n变化最大的 3 个格子（注意：变化大 ≠ 显著）")
    for d, k, p1, p2 in deltas[:3]:
        print("  %-10s%-16s %.0f%% → %.0f%%　差 %.0f 个百分点" %
              (k[0], k[1], p1 * 100, p2 * 100, d * 100))


if __name__ == "__main__":
    main()
