# -*- coding: utf-8 -*-
"""
seeds.py —— 从 W3 的载荷库里取种子

种子 = 自适应攻击的起点。PAIR 会拿它去改，所以种子不必很强，
但最好覆盖不同类别，这样能看到 attacker 往哪个方向演化。

用法：
    from seeds import load_seeds
    seeds = load_seeds()            # 全部
    seeds = load_seeds(limit=10)    # 前 10 条
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
W3_CODE = os.path.normpath(os.path.join(HERE, "..", "..", "W3", "02_代码"))
W3_PAYLOADS = os.path.join(W3_CODE, "payloads")

sys.path.insert(0, W3_CODE)

try:
    from runner import parse_pld          # 复用 W3 的解析器
except Exception as e:                    # 兜底：W3 被挪走时给出明确提示
    raise SystemExit("读不到 W3 的载荷解析器：%s\n请确认 %s 存在" % (e, W3_CODE))


def load_seeds(limit=None, categories=None):
    """返回 [{"id","category","body"}]，只保留 leak_canary 类的目标。"""
    out = []
    for fn in sorted(os.listdir(W3_PAYLOADS)):
        if not fn.endswith(".pld"):
            continue
        for item in parse_pld(os.path.join(W3_PAYLOADS, fn)):
            if item.get("goal") not in (None, "leak_canary", "leak_all", "leak_admin"):
                continue
            if categories and item.get("category") not in categories:
                continue
            body = item.get("body", "")
            # 多轮载荷只取第一轮，PAIR 的每一轮都是一次独立的单轮请求
            body = body.split("~~~")[0].strip()
            if not body:
                continue
            out.append({
                "id": item["id"],
                "category": item.get("category", ""),
                "body": body,
            })
    if limit:
        out = out[:limit]
    return out


if __name__ == "__main__":
    ss = load_seeds()
    print("共 %d 条种子" % len(ss))
    for s in ss[:5]:
        print("  %-8s %-10s %s" % (s["id"], s["category"], s["body"][:40]))
