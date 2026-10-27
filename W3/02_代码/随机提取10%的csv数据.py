import csv
import random
from pathlib import Path

INPUT_FILE = "../03_结果/results.csv"
OUTPUT_FILE = "../03_结果/results抽检.csv"
SAMPLE_RATE = 0.10
RANDOM_SEED = 42          # 固定种子，结果可复现；不需要可删掉

def main():
    with open(INPUT_FILE, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        print("文件为空")
        return

    header = rows[0]
    data = rows[1:]

    sample_size = max(1, round(len(data) * SAMPLE_RATE))
    sample_size = min(sample_size, len(data))

    random.seed(RANDOM_SEED)
    # 记录原索引，抽样后按原顺序输出（如需随机顺序可去掉 sorted）
    sampled_indices = sorted(random.sample(range(len(data)), sample_size))
    sampled = [data[i] for i in sampled_indices]

    with open(OUTPUT_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(sampled)

    print(f"总数据行: {len(data)}")
    print(f"抽取行数: {len(sampled)}")
    print(f"已保存: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()