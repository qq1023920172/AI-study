# -*- coding: utf-8 -*-
"""
mini_rag.py — 最小可用 RAG（漏洞标注版）

这个文件现在是 W1 的靶子：能跑，但不安全。
每一条 `⚠️ [LLMxx]` 都是你自己写出来的攻击面，W3 开始逐个打穿。

漏洞清单：
    V1  [LLM02] API key 硬编码
    V2  [LLM08] 知识库无权限隔离，所有人共享一个库
    V3  [LLM04/08] 入库无审核，任何文档都能进来
    V4  [LLM01] 检索结果原样拼进 prompt，无边界标记 ← 最重要
    V5  [LLM07] system prompt 写死在前端，可被套取
    V6  [LLM09] 检索无相似度阈值，永远返回 k 条
    V7  [LLM05] 输出无校验，直接交给下游
    V8  [LLM06] 一旦接入工具，这里就是权限放大器（预埋）
    V9  [LLM10] 无长度限制、无速率限制、无 max_tokens
    V10 [LLM02] 无日志无审计，被打了都不知道
"""
import sys
import numpy as np
from openai import OpenAI

# ⚠️ V1 [LLM02 敏感信息泄露]
# key 明文写在源码里，push 到 GitHub 就等于公开。
# 现在用的是本地 Ollama 占位符，所以只是"坏习惯"；换成真 key 就是事故。
# 正确做法：os.environ["API_KEY"] + .gitignore + pre-commit 密钥扫描。
client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

CHAT_MODEL = "qwen3:8b"
EMBED_MODEL = "bge-m3"


def embed(texts: list[str]) -> np.ndarray:
    # ⚠️ V9 [LLM10 无限制消费]
    # 没有 timeout、没有重试、没有单条长度上限。
    # 塞 100 万字进来会直接吃满内存；接口超时整个程序崩。
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    v = np.array([d.embedding for d in resp.data], dtype=np.float32)
    return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-8)


def chunk(text: str, size: int = 400, overlap: int = 80) -> list[str]:
    # ⚠️ 鲁棒性 bug：overlap >= size 时 step <= 0，range() 抛 ValueError。
    # 不是安全问题，但"能被输入搞崩的函数"本身就是 DoS 的雏形。
    step = size - overlap
    out = [text[i:i + size] for i in range(0, len(text), step)]
    return [c for c in out if c.strip()]


class Store:
    def __init__(self):
        self.chunks: list[str] = []
        self.vecs: np.ndarray | None = None

    def add(self, chunks: list[str]):
        # ⚠️ V3 [LLM04 投毒 / LLM08 向量弱点]
        # 入库零审核：谁调用 add()，谁就能往知识库塞内容。
        # 真实系统这里要有：来源校验、格式校验、恶意内容扫描、人工审核队列。
        #
        # ⚠️ V2 [LLM08 + LLM02]
        # 所有 chunk 进同一个库，没有 owner / tenant / 权限标签。
        # 结果就是：A 用户的私有文档，B 用户也能被检索到 —— RAG 越权泄露的根因。
        self.chunks += chunks
        v = embed(chunks)
        self.vecs = v if self.vecs is None else np.vstack([self.vecs, v])

    def search(self, q: str, k: int = 4):
        qv = embed([q])[0]
        # ⚠️ V6 [LLM09 错误信息]
        # 没有相似度阈值：哪怕最高分只有 0.29（完全不相关），也照样返回 4 条。
        # 模型拿到 4 段无关文本，又不敢说"不知道"，就开始编 —— 幻觉的第一现场。
        # 正确做法：if scores[idx[0]] < 0.45: return []，给它一个说"资料不足"的机会。
        scores = self.vecs @ qv          # 已归一化，点积即余弦相似度
        idx = np.argsort(-scores)[:k]
        return [(float(scores[i]), self.chunks[i]) for i in idx]


def answer(store: Store, question: str, k: int = 4) -> str:
    hits = store.search(question, k)   # ← LLM01：间接注入从这一行进入

    # ⚠️ V4 [LLM01 提示注入] ★ 全文件最重要的一处
    # 检索到的原文，用最朴素的字符串拼接塞进 prompt。三层问题：
    #   1. 没有「数据边界」标记 —— 模型分不清哪句是指令、哪句是资料
    #   2. 没有转义/过滤 —— 文档里写「忽略以上指令」会被当成真指令
    #   3. 没有来源标注 —— 出事追不到是哪份文档被投毒
    # 缓解方向：明确分隔符 + 声明"以下是不可信数据" + 保留来源 ID（不解决，只降影响）。
    ctx = "\n\n".join(
        f"[片段{i+1} | 相似度{s:.3f}]\n{c}" for i, (s, c) in enumerate(hits)
    )

    messages = [
        # ⚠️ V5 [LLM07 系统提示泄露]
        # 业务规则写死在 system prompt 里，而它迟早会被问出来。
        # 更糟的是：一旦把 API key、内网地址、过滤词表写进这里，泄露就是致命的。
        # 铁律：秘密不进 prompt。权限判断写在代码里，不写在提示里。
        {"role": "system",
         "content": "你是严谨的文档问答助手。只能依据【资料】回答；资料不足时"
                    "明确说「资料中没有提到」，禁止编造。管理员邮箱为：admin@qq.com。"},
        {"role": "user",
         "content": f"【资料】\n{ctx}\n\n【问题】\n{question}"},
    ]

    r = client.chat.completions.create(
        model=CHAT_MODEL, messages=messages, temperature=0
        # ⚠️ V9 [LLM10] 没有 max_tokens。用户可以诱导它一直生成，按 token 计费就爆了。
    )

    # ⚠️ V7 [LLM05 输出处理不当]（你已标注，补充一句）
    # 如果前端用 innerHTML 渲染，模型吐一个 <img onerror=...> 就是存储型 XSS。
    # 本质：**模型输出必须当成"用户输入"对待，不是当成"可信内容"。**
    return r.choices[0].message.content


# ⚠️ V8 [LLM06 过度代理] —— 预埋的坑
# 下一步你会给这个类加工具（读文件 / 发 HTTP / 查库）。
# 那一刻起，V4 的注入就从"说错话"升级成"替你执行操作"。
# 加工具时必须同时加：工具白名单、参数校验、最小权限、危险操作人工确认。


if __name__ == "__main__":
    # ⚠️ 路径写死（你之前指向 AI学习/，改名后会崩）。用相对路径更稳。
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.normpath(os.path.join(here, "..", "03_参考资料", "llm01-prompt-injection.txt"))
    text = open(filename, encoding="utf-8").read()

    # ⚠️ V10 [LLM02] 没有日志：谁、何时、问了什么、检索到哪几块、答了什么，全没记。
    # 真出了数据泄露，你连"泄露了什么"都说不清。审计日志是合规硬要求。
    store = Store()
    store.add(chunk(text))  # ← LLM04 投毒入口 / LLM08 向量污染入口
    print(f"入库 {len(store.chunks)} 个片段\n")

    while True:   # ← LLM10 无限提问
        q = input("问> ").strip()
        if q in {"", "exit", "quit"}:
            break
        # ⚠️ V9 [LLM10] 无输入长度限制：粘 100 万字进来，一次请求打满显存。
        print(answer(store, q), "\n")
