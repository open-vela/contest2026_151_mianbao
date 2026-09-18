"""把 InterviewForge_GenDS 数据集导入成本地题库（可重复运行）。

用法（在仓库根目录跑）：
  1. 拉取原始 CSV（huggingface.co 直连不通时用镜像）：
     curl -L -o /tmp/interview_forge.csv \
       https://hf-mirror.com/datasets/Davichick/InterviewForge_GenDS/resolve/main/interview_forge_v3_complete.csv
  2. python3 question_bank/import/import_dataset.py /tmp/interview_forge.csv

产物：question_bank/data/ai_questions.json（英文 AI 岗题，1647 道）

数据来源：https://huggingface.co/datasets/Davichick/InterviewForge_GenDS （MIT 许可）
说明：原始数据只有英文问题和关键词、没有参考答案（对模拟面试反而好——不会泄题）。
"""
import csv
import json
import pathlib
import sys

# 保留哪些岗位（子串匹配，小写）
AI_ROLE_KEYWORDS = ("ai/ml", "machine learning", "data scientist", "data analyst")
# 本文件在 question_bank/import/ 下，数据写进同级的 question_bank/data/
OUT_PATH = pathlib.Path(__file__).parent.parent / "data" / "ai_questions.json"


def main(source: str) -> None:
    rows = []
    with open(source, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            role = (row.get("role") or "").strip()
            if not any(key in role.lower() for key in AI_ROLE_KEYWORDS):
                continue
            keywords = row.get("keywords") or ""
            try:
                keyword_list = [k.strip() for k in eval(keywords) if str(k).strip()]  # 字段是 Python 列表字面量
            except Exception:
                keyword_list = [k.strip() for k in keywords.strip("[]").split(",") if k.strip()]
            rows.append({
                "question": (row.get("question") or "").strip(),
                "keywords": keyword_list,
                "role": role,
                "category": (row.get("question_category") or "").strip(),
                "level": (row.get("question_level") or "").strip(),
                "stage": (row.get("interview_stage") or "").strip(),
            })

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    roles = {}
    for row in rows:
        roles[row["role"]] = roles.get(row["role"], 0) + 1
    print(f"导入完成：{len(rows)} 条 → {OUT_PATH}")
    for role, count in sorted(roles.items(), key=lambda x: -x[1]):
        print(f"  {count:5d}  {role}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])
