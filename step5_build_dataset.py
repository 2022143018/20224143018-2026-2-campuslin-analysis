"""5단계: 검수 결과 → 학습 데이터셋 구축 + 라벨 품질 평가 + 베이스라인 모델

실행 순서
  python step5_build_dataset.py                 # 데이터셋 생성 + 평가
  python step5_build_dataset.py --make-recheck  # (선택) 재검수 시트 200건 생성
     → data/labeling/recheck_sheet.xlsx 의 label_recheck 를 '처음 라벨을 보지 않고' 채운 뒤
       다시 python step5_build_dataset.py 실행 → 검수자 내 일치도(kappa) 계산
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.worksheet.datavalidation import DataValidation
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, cohen_kappa_score, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split

import config

for name in ["Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR"]:
    if any(name == f.name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = name
        break
plt.rcParams["axes.unicode_minus"] = False

SHEET = os.path.join(config.DATA_LABELING, "labeling_sheet.xlsx")
RECHECK = os.path.join(config.DATA_LABELING, "recheck_sheet.xlsx")
SEED = 42


def load_checked():
    s = pd.read_excel(SHEET, dtype={"place_id": str})
    s["확인"] = s["확인"].fillna("").astype(str).str.strip().str.upper()
    s["label_final"] = s["label_final"].fillna("").astype(str).str.strip()
    checked = s[s["확인"] == "O"]
    valid = checked[checked["label_final"].isin(config.LABELS + [config.EXCLUDE])]
    return s, checked, valid


def make_recheck(valid):
    pick = valid.sample(n=min(200, len(valid)), random_state=7)
    wb = Workbook()
    ws = wb.active
    ws.title = "recheck"
    ws.append(["place_id", "place_name", "category_name", "kakao_url", "label_recheck"])
    for r in pick.itertuples():
        ws.append([r.place_id, r.place_name, r.category_name, r.kakao_url, ""])
    dv = DataValidation(type="list", formula1='"' + ",".join(config.LABELS + [config.EXCLUDE]) + '"')
    dv.add(f"E2:E{len(pick) + 1}")
    ws.add_data_validation(dv)
    for col, w in zip("ABCDE", [12, 26, 34, 34, 14]):
        ws.column_dimensions[col].width = w
    wb.save(RECHECK)
    print(f"재검수 시트 {len(pick)}건 → {RECHECK}")
    print("  최소 하루 뒤, 처음 라벨을 보지 말고 label_recheck 를 채운 다음 step5를 다시 실행하세요.")


def plot_cm(cm, labels, path, title):
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.imshow(cm, cmap="Oranges")
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_yticklabels(labels)
    ax.set_xlabel("최종 라벨 (검수)")
    ax.set_ylabel("자동 라벨 (규칙)")
    for i in range(len(labels)):
        for j in range(len(labels)):
            if cm[i, j]:
                ax.text(j, i, cm[i, j], ha="center", va="center", fontsize=8,
                        color="white" if cm[i, j] > cm.max() / 2 else "black")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def main():
    if not os.path.exists(SHEET):
        sys.exit("[오류] labeling_sheet.xlsx 가 없어요. step4 를 먼저 실행하세요.")
    sheet, checked, valid = load_checked()
    if "--make-recheck" in sys.argv:
        make_recheck(valid)
        return

    r = {"sheet_rows": len(sheet), "checked": len(checked), "valid": len(valid)}
    print(f"검수 시트 {len(sheet):,}건 중 확인(O) {len(checked):,}건, 유효 라벨 {len(valid):,}건")
    if len(valid) == 0:
        sys.exit("확인(O)된 행이 없어요. 엑셀에서 검수 후 저장하고 다시 실행하세요.")

    # ---- 자동 라벨 vs 사람 라벨 ----
    labs = config.LABELS + [config.EXCLUDE]
    r["changed"] = int((valid["label_auto"] != valid["label_final"]).sum())
    r["changed_pct"] = round(r["changed"] / len(valid) * 100, 1)
    r["rule_accuracy"] = round(accuracy_score(valid["label_final"], valid["label_auto"]) * 100, 1)
    r["rule_kappa"] = round(cohen_kappa_score(valid["label_final"], valid["label_auto"]), 3)
    r["rule_accuracy_by_conf"] = {
        k: round(float((g["label_auto"] == g["label_final"]).mean() * 100), 1)
        for k, g in valid.groupby("confidence")}
    r["rule_accuracy_by_label"] = {
        k: round(float((g["label_auto"] == g["label_final"]).mean() * 100), 1)
        for k, g in valid.groupby("label_auto")}
    ch = valid[valid["label_auto"] != valid["label_final"]]
    r["top_changes"] = (ch["label_auto"] + " → " + ch["label_final"]).value_counts().head(10).to_dict()
    cm = confusion_matrix(valid["label_auto"], valid["label_final"], labels=labs)
    pd.DataFrame(cm, index=[f"auto_{x}" for x in labs], columns=[f"final_{x}" for x in labs]).to_csv(
        os.path.join(config.REPORTS, "step5_confusion_rule.csv"), encoding="utf-8-sig")
    plot_cm(cm, labs, os.path.join(config.FIGURES, "07_confusion_rule_vs_human.png"), "자동 라벨 vs 검수 라벨")
    print(f"  규칙 라벨 정확도 {r['rule_accuracy']}% (kappa {r['rule_kappa']}), 수정 {r['changed']}건({r['changed_pct']}%)")

    # ---- 재검수 (검수자 내 일치도) ----
    if os.path.exists(RECHECK):
        rc = pd.read_excel(RECHECK, dtype={"place_id": str})
        rc["label_recheck"] = rc["label_recheck"].astype("object").where(rc["label_recheck"].notna(), "").astype(str).str.strip()
        rc = rc[rc["label_recheck"].isin(labs)]
        m = rc.merge(valid[["place_id", "label_final"]], on="place_id")
        if len(m):
            r["recheck_n"] = len(m)
            r["recheck_agree_pct"] = round(float((m["label_recheck"] == m["label_final"]).mean() * 100), 1)
            r["recheck_kappa"] = round(cohen_kappa_score(m["label_final"], m["label_recheck"]), 3)
            print(f"  재검수 {len(m)}건 일치율 {r['recheck_agree_pct']}% (kappa {r['recheck_kappa']})")

    # ---- 데이터셋 ----
    ds = valid[valid["label_final"] != config.EXCLUDE].copy()
    r["excluded"] = int((valid["label_final"] == config.EXCLUDE).sum())
    ds["text"] = ds["place_name"].astype(str) + " | " + ds["category_name"].astype(str)
    ds = ds.rename(columns={"label_final": "label"})
    keep = ["place_id", "place_name", "category_name", "area_type", "text", "label", "label_auto", "rule_id"]
    ds = ds[keep].reset_index(drop=True)
    os.makedirs(config.DATA_DATASET, exist_ok=True)
    ds.to_csv(os.path.join(config.DATA_DATASET, "train_dataset.csv"), index=False, encoding="utf-8-sig")
    r["dataset_size"] = len(ds)
    r["dataset_label_counts"] = ds["label"].value_counts().to_dict()

    # 층화 분할 (클래스당 2건 미만이면 층화 불가 → 랜덤)
    strat = ds["label"] if ds["label"].value_counts().min() >= 2 else None
    tr, va = train_test_split(ds, test_size=0.2, random_state=SEED, stratify=strat)
    tr.to_csv(os.path.join(config.DATA_DATASET, "train.csv"), index=False, encoding="utf-8-sig")
    va.to_csv(os.path.join(config.DATA_DATASET, "valid.csv"), index=False, encoding="utf-8-sig")
    r["train_size"], r["valid_size"] = len(tr), len(va)
    print(f"  데이터셋 {len(ds):,}건 (제외 {r['excluded']}건) → train {len(tr):,} / valid {len(va):,}")
    if len(ds) < 2000:
        print("  ⚠ 2,000건 미만이에요. 검수(확인 O)를 더 진행하세요.")

    # ---- 베이스라인: 규칙 vs TF-IDF + 로지스틱 회귀 (valid 기준) ----
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(1, 3), min_df=1)
    Xtr, Xva = vec.fit_transform(tr["text"]), vec.transform(va["text"])
    clf = LogisticRegression(max_iter=2000, class_weight="balanced")
    clf.fit(Xtr, tr["label"])
    pred = clf.predict(Xva)
    r["valid_rule_acc"] = round(accuracy_score(va["label"], va["label_auto"]) * 100, 1)
    r["valid_rule_f1"] = round(f1_score(va["label"], va["label_auto"], average="macro") * 100, 1)
    r["valid_model_acc"] = round(accuracy_score(va["label"], pred) * 100, 1)
    r["valid_model_f1"] = round(f1_score(va["label"], pred, average="macro") * 100, 1)
    print(f"  [valid] 규칙 정확도 {r['valid_rule_acc']}% / F1 {r['valid_rule_f1']}  vs  "
          f"모델 정확도 {r['valid_model_acc']}% / F1 {r['valid_model_f1']}")

    with open(os.path.join(config.REPORTS, "step5_dataset.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))


if __name__ == "__main__":
    main()
