# -*- coding: utf-8 -*-
"""
compare_retrievers.py —— 对照实验：词频检索 vs 向量检索

用法（在本文件所在目录）：
    python compare_retrievers.py

输出分三段：
    ① 索引地图：每块给一个编号 #0 #1 ...，后面只看编号
    ② 逐题对比：两种检索器各自选中的块编号、得分、是否命中
    ③ 汇总表：一眼看出谁在哪题上翻车
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import rag_zero as rz          # 词频版
import mini_rag as mr          # 向量版

# 用相对路径，换文件夹/换电脑都不会挂
HERE = os.path.dirname(os.path.abspath(__file__))
DOC = os.path.normpath(os.path.join(HERE, "..", "03_参考资料", "llm01-prompt-injection.txt"))

# (问题, 答案所在块里必然出现的关键词, 这题考什么)
# 关键词会匹配到"所有"含它的块（因为切分有重叠，同一段话可能出现在两块里），
# 命中任意一块即算对。
# 关键词为 None = 文档里没有答案，用来观察「分数的地板」。
CASES = [
    ("提示注入是什么", "改变LLM的行为", "字面重合，两个都该对"),
    ("怎么防御提示注入", "预防和缓解策略", "半语义：只共享「注入」两个字"),
    ("AI被坏人骗了怎么办", "预防和缓解策略", "★纯语义：提问和原文一个实词都不重合"),
    ("间接注入发生在哪里", "外部来源", "语义题：原文没有「哪里」"),
    ("系统提示词会泄露吗", "系统提示", "同义改写题"),
    ("为什么提示注入防不住", "万无一失", "抽象题：需要跨段推理"),
    ("越狱和提示注入什么关系", "越狱是提示注入的一种形式", "概念辨析题"),
    ("快速注入有哪些攻击场景", "攻击场景示例", "列举题：答案分散在多块"),
    ("火星上有没有生命", None, "无答案，看分数掉到多少"),
    ("今天午饭吃什么", None, "无答案，看分数掉到多少"),
]


def preview(c, n=26):
    return c.replace("\n", " ").strip()[:n]


def main():
    text = rz.read_text(DOC)
    chunks = rz.chunk(text, size=400, overlap=80)
    docs, df = rz.build_index(chunks)
    store = mr.Store()
    store.add(chunks)

    # ---------- ① 索引地图 ----------
    print(f"\n文档 {len(text)} 字 → 切成 {len(chunks)} 块（每块 400 字，重叠 80）")
    print("─" * 74)
    for i, c in enumerate(chunks):
        print(f"  #{i}  {preview(c, 34)}")
    print("─" * 74)

    rows = []
    same_top3 = 0

    # ---------- ② 逐题对比 ----------
    for qi, (q, kw, tag) in enumerate(CASES, 1):
        gold = set()
        if kw:
            gold = {i for i, c in enumerate(chunks) if kw in c}

        kw_hits = rz.retrieve(chunks, docs, df, q, k=3)
        ve_hits = store.search(q, k=3)
        kw_ids = [chunks.index(c) for _, c in kw_hits]
        ve_ids = [chunks.index(c) for _, c in ve_hits]

        if kw_ids == ve_ids:
            same_top3 += 1

        kw_ok = bool(gold) and bool(gold & set(kw_ids))
        ve_ok = bool(gold) and bool(gold & set(ve_ids))
        flag = "✓" if gold else "·"
        gtxt = ("标准答案在 " + "或".join(f"#{i}" for i in sorted(gold))) if gold else "文档里没有答案"

        print(f"\n问题 {qi}：{q}")
        print(f"  考点：{tag}　|　{gtxt}")
        print("  词频  " + "  ".join(f"#{i}({s:6.2f})" for (s, _), i in zip(kw_hits, kw_ids))
              + f"   {'✓' if kw_ok else ('✗' if gold else flag)}")
        print("  向量  " + "  ".join(f"#{i}({s:6.3f})" for (s, _), i in zip(ve_hits, ve_ids))
              + f"   {'✓' if ve_ok else ('✗' if gold else flag)}")

        rows.append((qi, q, gold, kw_ids, ve_ids, kw_ok, ve_ok))

    # ---------- ③ 汇总 ----------
    print("\n" + "═" * 74)
    print(f"{'#':<4}{'问题':<24}{'标准':<9}{'词频':<7}{'向量':<7}")
    for qi, q, gold, _, _, kw_ok, ve_ok in rows:
        g = "/".join(f"#{i}" for i in sorted(gold)) if gold else "—"
        print(f"{qi:<4}{q:<24}{g:<9}{'✓' if kw_ok else '✗':<7}{'✓' if ve_ok else '✗':<7}")

    scored = [r for r in rows if r[2]]
    print("─" * 74)
    print(f"Top-3 命中：词频 {sum(r[5] for r in scored)}/{len(scored)}　"
          f"向量 {sum(r[6] for r in scored)}/{len(scored)}")
    print(f"Top-1 命中：词频 {sum(1 for r in scored if r[2] & {r[3][0]})}/{len(scored)}　"
          f"向量 {sum(1 for r in scored if r[2] & {r[4][0]})}/{len(scored)}")
    print(f"Top-3 完全相同的题：{same_top3}/{len(rows)}")
    print("═" * 74)
    print("""
【观察任务】答案写进 02_代码/实验记录.md

1. 哪几题两者选中的块完全不同？它们有什么共同点？
2. 把两道「文档里没有答案」的题的最高分记下来，
   再和正常题的最高分比一比：
   哪一种检索器，能用「分数高低」判断出「我不知道」？
3. 只看 Top-1（不看 Top-3），两边各命中几题？
4. 结论写三行：现象 → 原因 → 对红队的意义
""")


if __name__ == "__main__":
    main()
