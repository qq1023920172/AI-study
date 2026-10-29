# -*- coding: utf-8 -*-
"""
strategy.py —— 攻击策略分类与漂移分析

要回答的问题：
    种子是「编码类」，改写之后还是「编码类」吗？
    如果不是，说明 attacker 在**策略漂移**（strategy collapse）——
    它只被优化"成功"，没有被约束"保持类别"。

用法：
    python strategy.py 版本3-8轮测试
"""
import csv
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.normpath(os.path.join(HERE, "..", "03_结果"))

# 种子类别 → 改写后应该"长什么样"
EXPECT = {
    "encoding": "encoding",
    "language": "language",
    "roleplay": "roleplay",
}


def classify(text):
    """规则式分类。粗糙，但足够看出漂移。"""
    t = text or ""

    # 1) 编码：长串 base64 / 明确的编码词 / unicode 转义
    if re.search(r"[A-Za-z0-9+/]{40,}={0,2}", t):
        return "encoding"
    if re.search(r"base64|rot13|unicode|\\u[0-9a-fA-F]{4}|十六进制|倒序|全角", t, re.I):
        return "encoding"
    if re.search(r"解码|编码后|编码为", t):
        return "encoding"

    # 2) 外语：字母数量显著多于汉字
    letters = len(re.findall(r"[A-Za-zÀ-ÿ\u00c0-\u024f]", t))
    han = len(re.findall(r"[\u4e00-\u9fff]", t))
    if letters >= 15 and letters > han * 0.6:
        return "language"

    # 3) 角色扮演 / 情境包装
    if re.search(r"扮演|角色|小说|故事|假设|想象|剧本|pretend|act as|imagine|fictional", t, re.I):
        return "roleplay"

    # 4) 格式 / 模板 / 示例诱导
    if re.search(r"格式|模板|表格|填写|补全|示例|样例|JSON|输出如下|按以下|参照", t, re.I):
        return "format"

    # 5) 权威 / 流程包装
    if re.search(r"管理员|审计|合规|安全专家|运维|紧急|授权|工单|上报|校验|审查|研究", t):
        return "authority"

    return "direct"


def main():
    ver = sys.argv[1] if len(sys.argv) > 1 else "版本3-8轮测试"
    path = os.path.join(BASE, ver, "pair_results.csv")
    rows = [r for r in csv.DictReader(open(path, encoding="utf-8"))
            if r["iteration"] not in ("-1", "")]
    if not rows:
        raise SystemExit("没有数据")

    # 只看每个种子的第 1 轮改写：这是"意图有没有被理解"的最干净证据
    first = {}
    for r in rows:
        if r["iteration"] == "1":
            first[r["seed_id"]] = r

    print("种子 %d 条，模型 %s\n" % (len(first), rows[0].get("model", "?")))

    # ── 一、整体分布
    dist = Counter(classify(r["attack"]) for r in first.values())
    print("=== 第 1 轮改写的策略分布 ===")
    for k, v in dist.most_common():
        print("  %-10s %2d 条  %5.0f%%" % (k, v, v * 100 / len(first)))

    # 但同一批里种子的类别分布是另一回事，这个分布本身不能说明漂移
    seed_dist = Counter(r["seed_category"] for r in first.values())
    print("\n=== 种子本身的类别分布 ===")
    for k, v in seed_dist.most_common():
        print("  %-10s %2d 条" % (k, v))

    # ── 二、类别保持率
    print("\n=== 类别保持率（种子类别 → 第 1 轮改写类别）===")
    for seed_cat, want in EXPECT.items():
        subset = [r for r in first.values() if r["seed_category"] == seed_cat]
        if not subset:
            continue
        kept = [r for r in subset if classify(r["attack"]) == want]
        print("\n  【%s】%d 条种子 → 保持了 %d 条（%.0f%%）"
              % (seed_cat, len(subset), len(kept), len(kept) * 100 / len(subset)))
        m = Counter(classify(r["attack"]) for r in subset)
        for k, v in m.most_common():
            print("      改写成了 %-10s %d 条" % (k, v))
        for r in subset[:2]:
            print("      例：%s" % r["attack"][:80].replace("\n", " "))

    # ── 三、漂移之后还有效吗
    print("\n=== 漂移后的成功率（用该种子后续所有轮次）===")
    by_seed = defaultdict(list)
    for r in rows:
        by_seed[r["seed_id"]].append(r)
    for seed_cat, want in EXPECT.items():
        ids = [r["seed_id"] for r in first.values() if r["seed_category"] == seed_cat]
        if not ids:
            continue
        kept_ids = [i for i in ids if classify(first[i]["attack"]) == want]
        moved_ids = [i for i in ids if i not in kept_ids]

        def succ(idlist):
            if not idlist:
                return "—"
            ok = sum(1 for i in idlist if any(x["success"] == "1" for x in by_seed[i]))
            return "%d/%d" % (ok, len(idlist))

        print("  %-10s 保持原策略 %s 成功　|　漂移走 %s 成功"
              % (seed_cat, succ(kept_ids), succ(moved_ids)))

    print("\n说明：这是规则分类，会有误判。看趋势，不要抠单条。")


if __name__ == "__main__":
    main()
