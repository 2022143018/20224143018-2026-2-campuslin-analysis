"""6단계: 각 단계 결과(json)를 모아 GitHub 보고서(README.md) 자동 작성

실행: python step6_build_report.py   (step1~5 실행 후)
"""
import json
import os

import pandas as pd
from scipy.stats import chi2_contingency

import config


def load(name):
    p = os.path.join(config.REPORTS, name)
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(out)


def n(v):
    return f"{v:,}" if isinstance(v, (int, float)) else str(v)


def main():
    p2, p3, p4, p5 = (load(x) for x in ["step2_preprocess.json", "step3_eda.json", "step4_label.json",
                                         "step5_dataset.json"])
    L = []
    L.append("# 캠슐랭 데이터 분석: 대학가 음식점 업종 구조와 학생 관점 업종 라벨링 데이터셋 구축\n")
    L.append("> 웹 서비스 **캠슐랭**(학교 인증 기반 대학가 맛집 지도)의 '음식 종류' 분류를 데이터로 뒷받침하기 위한 분석 프로젝트\n")

    # 1. 문제 정의 -------------------------------------------------
    L.append("## 1. 문제 정의 및 결론에 대한 가설\n")
    L.append("**문제 정의**\n")
    L.append("- 캠슐랭은 가게를 등록할 때 사용자가 음식 종류를 직접 고른다. 카카오 지도의 기본 분류는 "
             "'음식점 > 한식'처럼 얕거나, 학생들이 실제로 쓰는 구분(술집·분식·카페 등)과 맞지 않는 경우가 많다.")
    L.append("- 대학가 상권이 일반 상권과 실제로 다른 구조인지 데이터로 확인하고, 학생 관점의 업종 라벨 데이터셋을 만들어 "
             "가게 이름·분류만으로 업종을 자동 추천할 수 있는지 검증한다.\n")
    L.append("**가설**\n")
    L.append("- **H1.** 대학가(대학 반경 1km)는 일반 상권보다 분식·술집·카페·디저트 비중이 높다. (카이제곱 검정)")
    L.append("- **H2.** 카카오 기본 분류만으로는 학생 관점의 분류가 부족하다. → 2단계 이하의 얕은 분류 비율과 "
             "규칙 라벨의 오류율이 의미 있는 수준이다.")
    L.append("- **H3.** 검수한 라벨로 학습한 모델이 규칙 기반 라벨보다 정확하다. → 캠슐랭 가게 등록 시 업종 자동 추천에 활용\n")

    # 2. 데이터 양 -------------------------------------------------
    L.append("## 2. 확보한 데이터의 양\n")
    L.append("- 출처: **카카오 로컬 API**(공식 Open API) 카테고리 검색 — 음식점(FD6)·카페(CE7)")
    if p2:
        a = p2.get("areas", {})
        L.append(f"- 대상: 대학가 {a.get('대학가', '-')}곳 + 비교용 일반 상권(지하철역) {a.get('일반상권', '-')}곳, "
                 f"각 중심 반경 {config.RADIUS_KM:g}km")
        L.append("- 수집 방식: 반경을 덮는 사각형으로 검색하고, 결과가 45건(API 한도)을 넘으면 4등분하여 누락 없이 수집\n")
        L.append(table(["전처리 단계", "건수"], [(s, n(c)) for s, c in p2["steps"]]))
        L.append(f"\n**전처리 후 최종 {n(p2['final'])}건** "
                 + " / ".join(f"{k} {n(v)}건" for k, v in p2.get("by_area_type", {}).items()) + "\n")
    else:
        L.append("- (step2 결과 없음)\n")

    # 3. EDA -------------------------------------------------------
    L.append("## 3. 원본 데이터에 대한 EDA\n")
    if p3:
        L.append(f"- 원본 {n(p3['raw_rows'])}행, 고유 가게 {n(p3['raw_unique_places'])}곳 "
                 f"(여러 지역에 중복 수집된 행 {n(p3['raw_dup_rows'])}건)")
        L.append(f"- 컬럼: `{'`, `'.join(p3['raw_cols'])}`")
        L.append("- 빈 값 비율(%): " + ", ".join(f"{k} {v}" for k, v in p3["raw_blank"].items()))
        L.append(f"- 카카오 분류 깊이 분포: {p3['depth_counts']} → **2단계 이하(예: '음식점 > 한식')인 가게 "
                 f"{p3['shallow_pct']}%**")
        L.append(f"- 2단계 분류 종류 {p3['cat2_n_unique']}개, 3단계 {p3['cat3_n_unique']}개\n")
        titles = {"per_area": "지역별 가게 수 TOP 15", "per_area_hist": "지역당 가게 수 분포",
                  "top_cat2": "카카오 2단계 분류 TOP 20", "composition": "대학가 vs 일반상권 업종 구성",
                  "dist": "이름 길이·거리 분포", "scatter": "수집 위치"}
        for k, path in p3.get("figures", {}).items():
            L.append(f"**{titles.get(k, k)}**\n\n![{k}]({path})\n")
    else:
        L.append("- (step3 결과 없음)\n")

    # 4. 라벨 정의 --------------------------------------------------
    L.append("## 4. 데이터 라벨링에 대한 정의\n")
    L.append("- 라벨링 대상: 가게 1곳 = 1건, 입력 텍스트 = `가게 이름 | 카카오 분류`")
    L.append("- 라벨: 캠슐랭의 음식 종류를 학생 관점으로 세분화한 **10개 클래스 + 제외**")
    L.append("- 상세 기준과 경계 사례는 [`labeling_guide.md`](labeling_guide.md) 참고\n")
    from step4_auto_label import GUIDE
    L.append(table(["라벨", "정의", "예시"], GUIDE))
    L.append("")

    # 5. 라벨링 과정 ------------------------------------------------
    L.append("## 5. 데이터 라벨링 수행 과정\n")
    L.append("1. **규칙 기반 자동 라벨링 (전체)** — 카카오 분류 문자열에 키워드 규칙 R01~R09를 우선순위대로 적용, "
             "해당 없으면 '기타'(R00)")
    L.append("2. **신뢰도 표시** — 분류가 2단계 이하이거나, 규칙 미해당이거나, 가게 이름 단서와 충돌(예: 분류는 치킨인데 "
             "이름에 '호프')하면 `low`")
    L.append("3. **층화 표본 추출** — 라벨별 최소 150건을 보장하여 약 2,400건 추출 (random_state=42)")
    L.append(f"4. **검수 ({config.REVIEWER})** — 표본 전체를 가게 이름·카카오 분류를 보며 1건씩 확인하고 `label_final`(드롭다운)을 수정, "
             "확인 칸에 O 표시. `low` 행(노란색)을 먼저 검수")
    L.append("5. **품질 확인** — 자동 라벨 vs 최종 라벨 일치도(정확도, Cohen's kappa, 혼동행렬), "
             "(다음 단계) 사람이 표본을 독립적으로 다시 라벨링해 AI 검수와의 일치도(kappa) 측정")
    L.append("6. **데이터셋 구축** — '제외'를 뺀 확인 완료 행을 train/valid 8:2 층화 분할\n")
    if p4:
        rows = [(k, n(v), p4["label_auto_pct"].get(k, "")) for k, v in p4["label_auto_counts"].items()]
        L.append("**자동 라벨 결과 (전체)**\n")
        L.append(table(["라벨", "건수", "비율(%)"], rows))
        L.append(f"\n- 규칙 미해당('기타') {p4['label_auto_pct'].get('기타', 0)}%, 신뢰도 낮음 {p4['low_confidence_pct']}%, "
                 f"이름-분류 충돌 {p4['conflict_pct']}%")
        L.append(f"- 검수 표본 {n(p4['sample_size'])}건\n")

    # 6. 데이터셋 ---------------------------------------------------
    L.append("## 6. 라벨링 결과: 학습 데이터셋 구축\n")
    if p5:
        L.append(table(["항목", "값"], [
            ("검수 시트 행 수", n(p5["sheet_rows"])), ("검수 완료(확인 O)", n(p5["checked"])),
            ("제외 라벨", n(p5["excluded"])), ("**최종 데이터셋**", f"**{n(p5['dataset_size'])}건**"),
            ("train / valid", f"{n(p5['train_size'])} / {n(p5['valid_size'])}"),
            ("자동 라벨 수정 비율", f"{p5['changed_pct']}%"),
            ("자동 라벨 정확도 (kappa)", f"{p5['rule_accuracy']}% ({p5['rule_kappa']})"),
            ("사람 표본 vs 검수 라벨 일치율 (kappa)",
             f"{p5['recheck_agree_pct']}% ({p5['recheck_kappa']})" if "recheck_n" in p5 else "미실시 (다음 단계)"),
        ]))
        L.append("\n**라벨 분포**\n")
        L.append(table(["라벨", "건수"], list(p5["dataset_label_counts"].items())))
        if p5.get("top_changes"):
            L.append("\n**검수에서 가장 많이 고친 경우**\n")
            L.append(table(["자동 → 최종", "건수"], list(p5["top_changes"].items())))
        L.append("\n![confusion](reports/figures/07_confusion_rule_vs_human.png)\n")
        L.append("- 파일: `data/dataset/train_dataset.csv`, `train.csv`, `valid.csv` "
                 "(컬럼: place_id, place_name, category_name, area_type, text, label, label_auto, rule_id)\n")
    else:
        L.append("- (검수 후 step5 실행 필요)\n")

    # 가설 검증(중간) ----------------------------------------------
    L.append("## 7. 가설 검증 (중간 결과)\n")
    if p4.get("by_area_type_count"):
        ct = pd.DataFrame(p4["by_area_type_count"]).fillna(0)
        if ct.shape[1] == 2:
            chi2, pval, dof, _ = chi2_contingency(ct.values)
            pct = pd.DataFrame(p4["by_area_type"]).fillna(0)
            focus = [x for x in ["분식", "술집", "카페·디저트"] if x in pct.index]
            L.append(f"- **H1**: 업종 구성(자동 라벨 기준) 카이제곱 검정 χ²={chi2:,.1f}, df={dof}, p={pval:.2e} → "
                     + ("**유의함 (p<0.05)**" if pval < 0.05 else "유의하지 않음") + "\n")
            L.append(table(["라벨", "대학가(%)", "일반상권(%)"],
                           [(k, pct.loc[k].get("대학가", 0), pct.loc[k].get("일반상권", 0)) for k in focus]))
    if p3:
        L.append(f"\n- **H2**: 카카오 분류 2단계 이하 {p3['shallow_pct']}%"
                 + (f", 규칙 라벨이 검수 라벨과 다른 비율 {p5['changed_pct']}%" if p5 else ""))
    if p5:
        L.append(f"- **H3**: valid {n(p5['valid_size'])}건 기준 — 규칙 정확도 {p5['valid_rule_acc']}% (macro F1 "
                 f"{p5['valid_rule_f1']}) vs TF-IDF+로지스틱회귀 {p5['valid_model_acc']}% (macro F1 {p5['valid_model_f1']})")
    L.append("\n> 다음 단계: 데이터셋으로 분류 모델을 고도화하고, 캠슐랭 가게 등록 화면의 '음식 종류 자동 추천'에 적용\n")

    # 실행 방법 ----------------------------------------------------
    L.append("## 재현 방법\n")
    L.append("```bash\npip install -r requirements.txt\n# .env 에 KAKAO_REST_KEY=... (또는 ../campuslin/.env 사용)\n"
             "python step1_collect.py\npython step2_preprocess.py\npython step3_eda.py\npython step4_auto_label.py\n"
             "# data/labeling/labeling_sheet.xlsx 검수\npython step5_build_dataset.py\npython step6_build_report.py\n```\n")
    L.append("## 데이터 이용 안내\n")
    L.append("- 원본 데이터는 카카오 로컬 API로 수집했으며, 원본(`data/raw`)은 저장소에 올리지 않았다. "
             "API 키는 `.env`에만 보관한다.")

    with open(os.path.join(config.BASE_DIR, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("보고서 작성 완료 → README.md")


if __name__ == "__main__":
    main()
