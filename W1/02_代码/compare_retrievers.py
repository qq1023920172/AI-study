# -*- coding: utf-8 -*-
"""
compare_retrievers.py —— 对照实验：词频检索 vs 向量检索

用法（在本文件所在目录）：
    python compare_retrievers.py

它会做三件事：
    1. 用同一份文档、同样大小的切片，建两个索引（tf-idf / embedding）
    2. 用同一批问题，各取 top-3，并排打印
    3. 最后给出一个命中率对比：tf-idf 几个第一命中，embedding 几个

看结果的时候只盯一件事：
    「字面对不上、但语义对得上」的问题，谁答得对。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import rag_zero as rz          # 词频版：tokenize / chunk / build_index / retrieve
import mini_rag as mr          # 向量版：Store / embed

DOC = r"D:\ai\deepseek\AI学习\W1\03_参考资料\llm01-prompt-injection.txt"

# (问题, 答案里应该出现的关键词, 说明)
# 关键词为 None 表示「文档里没有答案」，用来测幻觉
CASES = [
    ("提示注入是什么", "提示注入", "字面高度重合，两个都应该答对"),
    ("怎么防御提示注入", "预防和缓解", "关键：tf-idf 之前在这题上翻车"),
    ("间接注入发生在哪里", "外部来源", "语义问题：文中没有「哪里」这个词"),
    ("系统提示词会泄露吗", "系统提示", "同义改写：原文说「基础设施或系统提示」"),
    ("为什么提示注入防不住", "万无一失", "抽象问题：需要跨段推理"),
    ("越狱和提示注入什么关系", "越狱", "概念辨析题"),
    ("火星上有没有生命", None, "文档里没有，看谁还在硬答"),
    ("今天午饭是什么", None, "文档里没有，看谁还在硬答"),
    ("今天午饭是什么", None, "文档里没有，看谁还在硬答"),
    ("提示注入漏洞的类型有哪些", "提示注入", "应该是两种才对"),
    ("快速注入有哪些攻击场景", "攻击场景", "越多越好"),
]


def mark(gold, chunk):
    if gold is None:
        return "·"
    return "✓" if gold in chunk else "✗"


def main():
    text = rz.read_text(DOC)
    chunks = rz.chunk(text, size=400, overlap=80)
    print(f"文档 {len(text)} 字，切成 {len(chunks)} 块\n")

    docs, df = rz.build_index(chunks)          # tf-idf 索引
    store = mr.Store()                         # 向量索引
    store.add(chunks)

    tf_hit = ve_hit = total = 0

    for q, gold, note in CASES:
        print("=" * 74)
        print(f"问题：{q}      （{note}）")

        kw = rz.retrieve(chunks, docs, df, q, k=3)
        ve = store.search(q, k=3)

        print("  [词频 tf-idf]")
        for i, (s, c) in enumerate(kw, 1):
            flat = c.replace("\n", " ")[:44]
            print(f"    {i}. {s:7.2f} {mark(gold, c)}  {flat}")

        print("  [向量 bge-m3]")
        for i, (s, c) in enumerate(ve, 1):
            flat = c.replace("\n", " ")[:44]
            print(f"    {i}. {s:7.3f} {mark(gold, c)}  {flat}")

        if gold is not None:
            total += 1
            tf_hit += 1 if gold in kw[0][1] else 0
            ve_hit += 1 if gold in ve[0][1] else 0
        print()

    print("=" * 74)
    print(f"Top-1 命中率：tf-idf {tf_hit}/{total}　向量 {ve_hit}/{total}")
    print("=" * 74)


if __name__ == "__main__":
    main()
