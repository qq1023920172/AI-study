# -*- coding: utf-8 -*-
"""
rejudge.py —— 只重判，不重跑

为什么需要它：
    改 judge.py 之后，正确做法是「拿同一批模型输出重新判一遍」，
    而不是「把模型也重跑一遍」。
    后者会让两个变量同时变：判定规则变了 + 模型输出也变了，
    于是你无法判断结果差异到底来自哪一个。

用法：
    python rejudge.py 版本1 版本1_rejudged
    （读取 03_结果/<输入版本>/results.csv，用当前 judge.py 重新判定，
      写到 03_结果/<输出版本>/）

限制：
    runner.py 把 response 截断到 200 字（防止 CSV 过大）。
    如果 canary 出现在 200 字之后，重判会漏掉。
    想彻底解决：把 runner.py 里的 [:200] 改成 [:1000] 再跑新数据。
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from judge import evaluate                     # noqa: E402
import runner                                  # noqa: E402  只为了读 payload 里的 judge 规则
from runner import parse_pld                   # noqa: E402

BASE = os.path.normpath(os.path.join(HERE, "..", "03_结果"))
PAYLOAD_DIR = os.path.join(HERE, "payloads")


def load_specs():
    """payload_id -> judge 规则"""
    specs = {}
    for fn in sorted(os.listdir(PAYLOAD_DIR)):
        if fn.endswith(".pld"):
            for item in parse_pld(os.path.join(PAYLOAD_DIR, fn)):
                specs[item["id"]] = item.get("judge", "")
    return specs


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "版本1"
    dst = sys.argv[2] if len(sys.argv) > 2 else src + "_rejudged"

    in_path = os.path.join(BASE, src, "results.csv")
    if not os.path.exists(in_path):
        raise SystemExit("找不到 " + in_path)

    specs = load_specs()
    rows = list(csv.DictReader(open(in_path, encoding="utf-8", newline="")))

    changed = 0
    for r in rows:
        spec = specs.get(r["payload_id"], "")
        ok, refused = evaluate(spec, r["response"])
        if int(r["success"]) != int(ok):
            changed += 1
        r["success"] = int(ok)
        r["refused"] = int(refused)

    os.makedirs(os.path.join(BASE, dst), exist_ok=True)
    out_path = os.path.join(BASE, dst, "results.csv")
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    total = len(rows)
    asr = sum(int(r["success"]) for r in rows) / total
    print("重判完成：%d 条，判定结果改变 %d 条（%.1f%%）" %
          (total, changed, changed * 100 / total))
    print("新的 ASR：%.0f%%" % (asr * 100))
    print("输出：%s" % out_path)
    print("\n下一步：用同一份 CSV 生成矩阵前，先改 matrix.py 的输入路径，")
    print("或者把新 CSV 复制到 版本1/ 覆盖（不推荐，保留原始结果更好）。")


if __name__ == "__main__":
    main()
