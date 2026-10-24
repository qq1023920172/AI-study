"""
mini_rag.py — 最小可用 RAG
用法: python mini_rag.py 你的文档.txt
"""
import sys
import numpy as np
from openai import OpenAI


# Ollama 的 OpenAI 兼容端点
client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
CHAT_MODEL = "qwen3:8b"
EMBED_MODEL = "bge-m3"


def embed(texts: list[str]) -> np.ndarray:
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    v = np.array([d.embedding for d in resp.data], dtype=np.float32)
    return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-8)


def chunk(text: str, size: int = 400, overlap: int = 80) -> list[str]:
    step = size - overlap
    out = [text[i:i + size] for i in range(0, len(text), step)]
    return [c for c in out if c.strip()]


class Store:
    def __init__(self):
        self.chunks: list[str] = []
        self.vecs: np.ndarray | None = None

    def add(self, chunks: list[str]):
        self.chunks += chunks
        v = embed(chunks)
        self.vecs = v if self.vecs is None else np.vstack([self.vecs, v])

    def search(self, q: str, k: int = 4):
        qv = embed([q])[0]
        scores = self.vecs @ qv          # 已归一化，点积即余弦相似度
        idx = np.argsort(-scores)[:k]
        return [(float(scores[i]), self.chunks[i]) for i in idx]


def answer(store: Store, question: str, k: int = 4) -> str:
    hits = store.search(question, k)   # LLM01通过RAG数据库间接注入
    ctx = "\n\n".join(
        f"[片段{i+1} | 相似度{s:.3f}]\n{c}" for i, (s, c) in enumerate(hits)
    )
    messages = [
        {"role": "system",
         "content": "你是严谨的文档问答助手。只能依据【资料】回答；资料不足时"
                    "明确说「资料中没有提到」，禁止编造。"},
        {"role": "user",
         "content": f"【资料】\n{ctx}\n\n【问题】\n{question}"},
    ]
    r = client.chat.completions.create(
        model=CHAT_MODEL, messages=messages, temperature=0
    )
    return r.choices[0].message.content   # LLM05 输出处理不当，未经处理


if __name__ == "__main__":
    filename = r"D:\ai\deepseek\AI学习\W1\03_参考资料\llm01-prompt-injection.txt"
    text = open(filename, encoding="utf-8").read()
    store = Store()
    store.add(chunk(text))  # LLM04 数据不可信未处理/LLM08向量检索易受到污染
    print(f"入库 {len(store.chunks)} 个片段\n")
    while True:
        q = input("问> ").strip()
        if q in {"", "exit", "quit"}:
            break
        print(answer(store, q), "\n")
