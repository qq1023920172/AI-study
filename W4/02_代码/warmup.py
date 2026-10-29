# -*- coding: utf-8 -*-
"""
warmup.py —— 把多个模型同时拉进显存，并验证它们真的驻留了

解决的问题：
    Ollama 默认只让少量模型同时驻留，attacker / target 交替调用时会
    「卸载 A → 加载 B → 卸载 B → 加载 A」，每轮白扔十几秒。

用法：
    python warmup.py                       # 预热 deepseek-r1:14b + qwen3:8b
    python warmup.py --check               # 只看当前驻留情况，不加载
    python warmup.py --models qwen3:8b     # 只预热一个
    python warmup.py --ctx 2048            # 指定上下文长度（默认 2048）

前置（设完必须重启 Ollama）：
    setx OLLAMA_MAX_LOADED_MODELS 2
    setx OLLAMA_KEEP_ALIVE -1
    setx OLLAMA_NUM_PARALLEL 1
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request

HOST = "http://localhost:11434"
DEFAULT_MODELS = ["deepseek-r1:14b", "qwen3:8b"]


def _get(path, timeout=10):
    with urllib.request.urlopen(HOST + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _post(path, payload, timeout=300):
    req = urllib.request.Request(
        HOST + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def show_ps(title="当前驻留情况"):
    try:
        data = _get("/api/ps")
    except Exception as e:
        print("读不到 /api/ps：%s" % e)
        return []

    models = data.get("models", [])
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)
    if not models:
        print("  （没有任何模型驻留）")
        return []

    total_vram = 0
    for m in models:
        name = m.get("name") or m.get("model", "?")
        size = m.get("size", 0) / 1e9
        vram = m.get("size_vram", 0) / 1e9
        total_vram += vram
        pct = (vram / size * 100) if size else 0
        flag = "✓ 全在显存" if pct > 98 else "⚠ 有层落到内存（会明显变慢）"
        print("  %-20s 权重 %5.1f GB | 显存 %5.1f GB (%3.0f%%)  %s"
              % (name, size, vram, pct, flag))
        exp = m.get("expires_at", "")
        print("  %-20s 过期时间：%s" % ("", exp))

    print("  " + "─" * 66)
    print("  合计占用显存：%.1f GB" % total_vram)
    print("=" * 72)
    return models


def warm(model, ctx=2048, keep_alive=-1):
    """用最小的请求把模型拉进显存，并设置保活时间。"""
    t0 = time.time()
    try:
        _post("/api/generate", {
            "model": model,
            "prompt": "hi",
            "stream": False,
            "keep_alive": keep_alive,
            "options": {"num_ctx": ctx, "num_predict": 1},
        })
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:200]
        print("  ✗ %-20s 加载失败：HTTP %s %s" % (model, e.code, body))
        return False
    except Exception as e:
        print("  ✗ %-20s 加载失败：%s" % (model, e))
        return False
    print("  ✓ %-20s 已加载（%.1fs）" % (model, time.time() - t0))
    return True


def diagnose(loaded, wanted):
    names = " ".join((m.get("name") or "") for m in loaded)
    print("\n【诊断】")
    if len(loaded) < len(wanted):
        print("  ✗ 只驻留了 %d 个，期望 %d 个" % (len(loaded), len(wanted)))
        print("    → 多半是 OLLAMA_MAX_LOADED_MODELS 没生效。检查：")
        print("      1) setx OLLAMA_MAX_LOADED_MODELS 2 是否执行")
        print("      2) Ollama 是否**完全退出后重启**（托盘 → Quit → 再打开）")
        print("      3) 显存不足时 Ollama 仍会驱逐，先看下面的占用")
    else:
        print("  ✓ %d 个模型全部驻留" % len(loaded))

    for m in loaded:
        size = m.get("size", 0)
        vram = m.get("size_vram", 0)
        if size and vram / size < 0.98:
            print("  ⚠ %s 有 %.0f%% 的层不在显存（CPU 卸载），推理会慢 3–10 倍"
                  % (m.get("name", "?"), (1 - vram / size) * 100))

    exp = [m.get("expires_at", "") for m in loaded]
    if exp and all(e[:4] and e[:4] < "2100" for e in exp):
        print("  ⚠ 过期时间是具体时刻，说明 KEEP_ALIVE 没设成 -1（默认 5 分钟后回收）")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS))
    ap.add_argument("--ctx", type=int, default=2048)
    ap.add_argument("--check", action="store_true", help="只查看，不加载")
    args = ap.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]

    try:
        ver = _get("/api/version").get("version", "?")
        print("Ollama 在线，版本 %s" % ver)
    except Exception as e:
        raise SystemExit("连不上 Ollama（%s）。先确认它在运行。" % e)

    if args.check:
        show_ps("当前驻留情况（--check，未加载任何模型）")
        return

    print("\n开始预热（num_ctx=%d，keep_alive=-1）" % args.ctx)
    for m in models:
        warm(m, ctx=args.ctx)

    time.sleep(1)
    loaded = show_ps()
    diagnose(loaded, models)

    print("提示：跑 pair.py 之前先执行一次本脚本，两个模型就不会来回换进换出了。\n")


if __name__ == "__main__":
    main()
