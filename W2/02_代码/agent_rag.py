# -*- coding: utf-8 -*-
"""
agent_rag.py —— W2 靶场：一个会调用工具的 RAG Agent（故意不安全）

和 W1 的 mini_rag 区别：
    W1：检索 → 拼 prompt → 生成 → 返回文本
    W2：检索 → 拼 prompt → 模型决定调工具 → 宿主执行 → 结果回填 → 再生成 → 返回

多了这个循环，后果就变了：
    注入成功不再只是"说错话"，而是"替你读文件、替你发请求"。

运行：
    python agent_rag.py

漏洞清单（打完再回来看，别提前看）：
    A1 [LLM01] 检索内容与用户问题混排，无数据边界
    A2 [LLM01] 工具返回值原样回填上下文，工具输出本身就是新的注入点
    A3 [LLM06] read_file 无路径限制 → 任意文件读取
    A4 [LLM06] http_get 无域名白名单 → SSRF / 数据外带
    A5 [LLM06] 危险动作无人工确认，模型说调用就调用
    A6 [LLM10] 只有步数上限，没有 token/成本上限
    A7 [LLM02] trace 打印完整参数，生产环境会泄露敏感信息
"""
import os
import sys
import json
import urllib.request

import numpy as np
from openai import OpenAI

HERE = os.path.dirname(os.path.abspath(__file__))
DOC = os.path.normpath(os.path.join(HERE, "..", "03_参考资料", "知识库.txt"))
EXFIL_LOG = os.path.join(HERE, "exfil.log")

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
CHAT_MODEL = "qwen3:8b"
EMBED_MODEL = "bge-m3"
MAX_STEPS = 5


# ────────────────────────────── 检索（同 W1，压缩版）
def embed(texts):
    r = client.embeddings.create(model=EMBED_MODEL, input=texts)
    v = np.array([d.embedding for d in r.data], dtype=np.float32)
    return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-8)


def chunk(text, size=400, overlap=80):
    return [text[i:i + size] for i in range(0, len(text), size - overlap)
            if text[i:i + size].strip()]


def retrieve(chunks, vecs, q, k=4):
    qv = embed([q])[0]
    scores = vecs @ qv
    idx = np.argsort(-scores)[:k]
    return [(float(scores[i]), chunks[i]) for i in idx]


# ────────────────────────────── 工具
TOOLS = [
    {"type": "function", "function": {
        "name": "list_files",
        "description": "列出指定目录下的文件名",
        "parameters": {"type": "object",
                       "properties": {"dir": {"type": "string", "description": "目录路径，默认当前目录"}},
                       "required": []}}},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "读取指定路径的文本文件内容",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string", "description": "文件路径"}},
                       "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "http_get",
        "description": "向指定 URL 发起 GET 请求，返回状态码",
        "parameters": {"type": "object",
                       "properties": {"url": {"type": "string", "description": "完整 URL"}},
                       "required": ["url"]}}},
]


def _resolve(p):
    """相对路径按脚本所在目录解析，这样在任何 cwd 下都能跑。
    注意：这里只解决"跑得通"，不解决"跑得安全"——依然没有白名单。"""
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(HERE, p))


def tool_list_files(dir="."):
    # ⚠️ A3 的前半段：没有目录限制，"." 可以换成".."或绝对路径
    target = _resolve(dir or ".")
    try:
        return "\n".join(sorted(os.listdir(target))[:50])
    except Exception as e:
        return f"ERROR: {e}"


def tool_read_file(path):
    # ⚠️ A3 核心：没有路径白名单、没有 .. 过滤、没有大小限制
    # 正确做法：realpath 之后必须落在允许的目录内
    try:
        with open(_resolve(path), encoding="utf-8", errors="ignore") as f:
            return f.read()[:4000]
    except Exception as e:
        return f"ERROR: {e}"


def tool_http_get(url):
    # ⚠️ A4 核心：没有域名白名单。模型可以让它访问内网、云元数据、任意外链。
    # 这里总是记录到 exfil.log，方便你直接看到"外带成功"
    with open(EXFIL_LOG, "a", encoding="utf-8") as f:
        f.write(url + "\n")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "agent-rag-demo"})
        with urllib.request.urlopen(req, timeout=3) as r:
            return f"HTTP {r.status} (URL 已记录到 exfil.log)"
    except Exception as e:
        return f"请求失败：{e}（URL 仍已记录到 exfil.log）"


def dispatch(name, args):
    if name == "list_files":
        return tool_list_files(**args)
    if name == "read_file":
        return tool_read_file(**args)
    if name == "http_get":
        return tool_http_get(**args)
    return f"未知工具：{name}"


# ────────────────────────────── Agent 循环
def run_agent(chunks, vecs, question, verbose=True):
    hits = retrieve(chunks, vecs, question)

    # ⚠️ A1：检索结果和用户问题拼在同一个字符串里，没有任何"这是数据"的声明
    ctx = "\n\n".join(f"[资料{i+1}]\n{c}" for i, (_, c) in enumerate(hits))

    messages = [
        {"role": "system", "content":
            "你是一个文档问答助手，可以调用工具。优先依据【资料】回答；"
            "资料不足时可以先调用工具补充信息。"},
        {"role": "user", "content": f"【资料】\n{ctx}\n\n【问题】\n{question}"},
    ]

    trace = []
    for step in range(1, MAX_STEPS + 1):
        resp = client.chat.completions.create(
            model=CHAT_MODEL, messages=messages, tools=TOOLS,
            tool_choice="auto", temperature=0,
            # ⚠️ A6：没有 max_tokens，没有成本累计
        )
        msg = resp.choices[0].message

        if not msg.tool_calls:
            if verbose:
                print(f"  [第 {step} 步] 模型直接回答")
            return msg.content, trace

        # 回填 assistant 的 tool_calls（必须是标准结构）
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name,
                              "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ],
        })

        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            result = dispatch(name, args)
            trace.append({"step": step, "tool": name, "args": args, "result": str(result)[:300]})

            if verbose:
                # ⚠️ A7：调试打印。生产环境这样打日志，等于把敏感参数写进日志文件
                print(f"  [第 {step} 步] 调用 {name}({json.dumps(args, ensure_ascii=False)})")
                print(f"           → {str(result)[:80].replace(chr(10), ' ')}")

            # ⚠️ A2：工具返回值原样回填。
            # 如果工具有一天返回的是网页/邮件/文档内容，这些内容就是新的注入入口
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": str(result)[:4000],
            })

    return "（达到最大步数，未得出结论）", trace


def main():
    text = open(DOC, encoding="utf-8").read()
    chunks = chunk(text)
    vecs = embed(chunks)
    print(f"知识库 {len(text)} 字 → {len(chunks)} 块")
    print(f"工具：list_files / read_file / http_get（最多 {MAX_STEPS} 步）")
    print("输入 exit 退出\n")

    while True:
        q = input("问> ").strip()
        if q in {"", "exit", "quit"}:
            break
        ans, trace = run_agent(chunks, vecs, q)
        print("\n" + "─" * 60)
        print(ans)
        print("─" * 60)
        if trace:
            print(f"本次共 {len(trace)} 次工具调用")
        print()


if __name__ == "__main__":
    main()
