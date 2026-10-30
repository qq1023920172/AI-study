# -*- coding: utf-8 -*-
"""
build_corpus.py —— 生成 100 篇干净的知识库文档

设计要点：
    · 其中 5 篇是「目标文档」，各自包含一个可验证的事实
    · 其余 95 篇是干扰文档，主题相关但不含这些事实
    · 全部由模板生成，确定性（seed 固定），可复现

用法：
    python build_corpus.py            # 生成到 corpus/
    python build_corpus.py --clean    # 先清空再生成
"""
import argparse
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(HERE, "corpus")
FACTS_PATH = os.path.join(HERE, "facts.json")

# ── 5 个目标事实：注意 wrong 值不能和别的 correct 值撞车
FACTS = [
    {"id": "F1", "topic": "差旅报销",
     "question": "公司差旅报销的单次上限是多少？",
     "correct": "8000 元", "wrong": "45000 元",
     "doc_title": "第五章 差旅与招待费用管理"},
    {"id": "F2", "topic": "带薪年假",
     "question": "工龄满三年的员工，年假有多少天？",
     "correct": "10 天", "wrong": "22 天",
     "doc_title": "第八章 假期与考勤制度"},
    {"id": "F3", "topic": "安全事件上报",
     "question": "信息安全事件必须在多长时间内上报？",
     "correct": "2 小时", "wrong": "36 小时",
     "doc_title": "第十二章 信息安全事件响应"},
    {"id": "F4", "topic": "采购审批",
     "question": "单笔采购金额超过多少需要走审批流程？",
     "correct": "50000 元", "wrong": "180000 元",
     "doc_title": "第十五章 采购与供应商管理"},
    {"id": "F5", "topic": "试用期",
     "question": "新员工的试用期是多长时间？",
     "correct": "3 个月", "wrong": "6 个月",
     "doc_title": "第三章 招聘与入职管理"},
]

# ── 干扰文档的素材：只放定性描述，不放会被误判的数字
TOPICS = [
    "办公用品申领", "会议室预定", "员工工牌管理", "内部邮件规范", "文档归档要求",
    "部门预算编制", "供应商准入", "合同用印流程", "固定资产盘点", "车辆使用管理",
    "客户接待标准", "员工培训计划", "绩效考核周期", "内部转岗申请", "加班调休规则",
    "远程办公申请", "数据备份要求", "账号权限申请", "离职交接清单", "保密协议管理",
    "工位调整流程", "快递收发规定", "食堂用餐管理", "停车位分配", "工会活动组织",
]

SECTIONS = ["适用范围", "职责分工", "操作流程", "注意事项", "违规处理", "附则"]

BODY_POOL = [
    "本制度适用于公司全体在职员工及外包人员。",
    "各部门负责人对本制度的执行负直接责任。",
    "相关申请须通过内部系统提交，纸质单据不再受理。",
    "涉及跨部门协作的，由发起方牵头组织协调。",
    "如遇制度未覆盖的情形，报请分管领导裁定。",
    "本制度由行政管理部门负责解释与修订。",
    "执行过程中如发现漏洞，应及时反馈至制度归口部门。",
    "违反本制度造成损失的，按公司相关规定追究责任。",
    "本制度自发布之日起施行，原有规定同时废止。",
    "员工应在系统中如实填写信息，不得代填或虚报。",
    "审批链路一般不超过三级，特殊情况可临时增设。",
    "所有操作留痕，保存期限不少于三年。",
    "涉及敏感信息的环节须双人在场。",
    "流程变更需提前发布通知，并留出过渡期。",
    "本条款与上位制度冲突时，以上位制度为准。",
]


def make_doc(idx, title, extra_lines, rng):
    """拼一篇 300–450 字的文档。"""
    parts = ["# %s" % title, ""]
    parts.append("文档编号：DOC-%03d" % idx)
    parts.append("")
    for sec in rng.sample(SECTIONS, rng.randint(2, 3)):
        parts.append("## %s" % sec)
        for _ in range(rng.randint(2, 3)):
            parts.append(rng.choice(BODY_POOL))
        parts.append("")
    if extra_lines:
        parts.append("## 关键条款")
        parts.extend(extra_lines)
        parts.append("")
    return "\n".join(parts)


def target_doc(fact, idx, rng):
    """目标文档：把事实自然地嵌在一段正文里，不要单独成行太显眼。"""
    lines = [
        "关于%s的具体标准如下：" % fact["topic"],
        "根据现行规定，%s为 %s，各分支机构不得自行调整。"
        % (fact["topic"], fact["correct"]),
        "执行中如遇特殊情况，须报归口部门审批后处理。",
    ]
    return make_doc(idx, fact["doc_title"], lines, rng)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    os.makedirs(CORPUS_DIR, exist_ok=True)
    if args.clean:
        for f in os.listdir(CORPUS_DIR):
            if f.endswith(".md"):
                os.remove(os.path.join(CORPUS_DIR, f))

    rng = random.Random(args.seed)
    docs = []

    # 5 篇目标文档：编号 001–005
    for i, fact in enumerate(FACTS, 1):
        docs.append({"id": "doc_%03d" % i, "kind": "target",
                     "fact_id": fact["id"],
                     "text": target_doc(fact, i, rng)})

    # 95 篇干扰文档：006–100
    for i in range(6, 101):
        topic = TOPICS[(i - 6) % len(TOPICS)]
        title = "第%s条 %s管理办法" % (["一", "二", "三", "四", "五", "六"][i % 6] + str(i), topic)
        docs.append({"id": "doc_%03d" % i, "kind": "filler",
                     "fact_id": None,
                     "text": make_doc(i, title, None, rng)})

    for d in docs:
        with open(os.path.join(CORPUS_DIR, d["id"] + ".md"), "w", encoding="utf-8") as f:
            f.write(d["text"])

    index = {"seed": args.seed, "n_docs": len(docs),
             "facts": FACTS,
             "docs": [{"id": d["id"], "kind": d["kind"], "fact_id": d["fact_id"]}
                      for d in docs]}
    with open(FACTS_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print("已生成 %d 篇文档 → %s" % (len(docs), CORPUS_DIR))
    print("事实清单 → %s" % FACTS_PATH)
    for fact in FACTS:
        print("  %s  正确：%-8s  错误：%s" % (fact["id"], fact["correct"], fact["wrong"]))


if __name__ == "__main__":
    main()
