# -*- coding: utf-8 -*-
"""
rag_zero.py —— 零依赖版 RAG 检索演示

不需要装任何第三方包，不需要下载模型。用法：

    python rag_zero.py 你的文档.txt

目的：让你亲眼看到「RAG 的检索」到底是什么。
它不是魔法，就是三件事：
    1. 把文档切成块
    2. 把每块转成一组数字（这里是词频，后面会换成向量）
    3. 按相似度排序，取前 k 块

看懂这一百多行，你就理解了 RAG 的骨架。
真正的「embedding 检索」只是把第 2 步换成一个更好的表示方法而已。
"""
import sys
import math
import re
from collections import Counter


def tokenize(text: str) -> list[str]:
    """粗粒度分词：英文数字按词，中文按单字。够用就行。"""
    text = text.lower()
    text = text.replace("的", " ").replace("了", " ").replace("是", " ")
    words = re.findall(r"[a-z0-9_]+", text)
    chars = re.findall(r"[\u4e00-\u9fff]", text)
    return words + chars


def chunk(text: str, size: int = 200, overlap: int = 40) -> list[str]:
    """按固定长度切块，块与块之间留 overlap，避免句子被切断。"""
    step = size - overlap
    out = []
    for i in range(0, len(text), step):
        piece = text[i:i + size]
        if piece.strip():
            out.append(piece)
    return out


def build_index(chunks: list[str]):
    """把每块变成词袋，并统计每个词出现在多少块里（用于算 IDF）。"""
    docs = [tokenize(c) for c in chunks]
    df = Counter()
    for d in docs:
        for t in set(d):
            df[t] += 1
    return docs, df


def score(query_tokens, doc_tokens, df, n_docs) -> float:
    """简化版 TF-IDF：一个词越罕见、在这块里出现越多，这块就越相关。"""
    tf = Counter(doc_tokens)
    total = 0.0
    for t in set(query_tokens):
        if t not in tf:
            continue
        idf = math.log((n_docs + 1) / (df.get(t, 1) + 1)) + 1.0
        total += (1 + math.log(tf[t])) * idf
    return total


def retrieve(chunks, docs, df, query: str, k: int = 3):
    q = tokenize(query)
    ranked = [(score(q, d, df, len(docs)), c) for d, c in zip(docs, chunks)]
    ranked.sort(key=lambda x: -x[0])
    return ranked[:k]


def show(chunks, docs, df, query: str, k: int = 3):
    hits = retrieve(chunks, docs, df, query, k)
    print(f"\n问：{query}")
    for i, (s, c) in enumerate(hits, 1):
        flat = c.replace("\n", " ")
        print(f"  [{i}] 得分 {s:6.2f} | {flat[:56]}...")

    ctx = "\n\n".join(f"[片段{i}] {c}" for i, (s, c) in enumerate(hits, 1))
    # print("  ── 下面这段会被拼进 prompt 送给大模型 ──")
    # print("  " + ctx[:300].replace("\n", "\n  ") + ("..." if len(ctx) > 300 else ""))
    # print()


def read_text(path: str) -> str:
    """Windows 上的 txt 可能是 UTF-8 带 BOM，也可能是 GBK，都试一遍。"""
    for enc in ("utf-8-sig", "gbk"):
        try:
            with open(path, encoding=enc) as fh:
                return fh.read()
        except UnicodeDecodeError:
            continue
    with open(path, encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def main():
    # if len(sys.argv) < 2:
    #     print(__doc__)
    #     return
    filename = r"D:\ai\deepseek\AI学习\W1\03_参考资料\llm01-prompt-injection.txt"
    text = read_text(filename)

    chunks = chunk(text)
    docs, df = build_index(chunks)
    print(f"文档 {len(text)} 字，切成 {len(chunks)} 块，词表 {len(df)} 个。")

    # 三个预设问题，直接跑一遍看效果
    show(chunks, docs, df, "怎么防御")
    show(chunks, docs, df, "什么是间接注入")
    # 这个问题文档里大概率没有，注意看它是不是照样返回了结果
    show(chunks, docs, df, "火星上有没有生命")

    while True:
        try:
            q = input("问> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q in {"", "exit", "quit"}:
            break
        show(chunks, docs, df, q)


if __name__ == "__main__":
    main()
