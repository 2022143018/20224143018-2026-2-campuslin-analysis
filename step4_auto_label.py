"""4단계: 규칙 기반 자동 라벨링 + 수동 검수용 시트 만들기

1) 카카오 분류(category_name)에 config.RULES 를 위에서부터 적용 → label_auto
2) 가게 이름에 다른 라벨 단서가 있으면 '충돌'로 표시 (검수 때 먼저 보도록)
3) 라벨별 층화 표본 약 2,400건 추출 → data/labeling/labeling_sheet.xlsx
   (label_final 드롭다운, 확인 칸에 O 입력)

실행: python step4_auto_label.py
"""
import json
import os
import sys

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

import config

SAMPLE_TOTAL = 2400
MIN_PER_CLASS = 150
SEED = 42

# 가게 이름에 들어 있으면 해당 라벨일 가능성이 높은 단서 (충돌 검사용)
NAME_HINTS = {
    "술집": ["호프", "포차", "주점", "이자카야", "펍", "PUB", "비어", "BAR", "바 ", "술"],
    "카페·디저트": ["카페", "커피", "COFFEE", "CAFE", "베이커리", "디저트", "빵"],
    "치킨": ["치킨", "통닭"],
    "분식": ["김밥", "떡볶이", "분식", "토스트"],
    "중식": ["반점", "마라", "짬뽕", "양꼬치"],
    "일식": ["스시", "초밥", "라멘", "돈까스", "돈카츠", "우동"],
    "양식": ["피자", "버거", "파스타", "스테이크"],
    "아시안": ["쌀국수", "포 ", "타이", "커리"],
}


def auto_label(category):
    for rid, label, words in config.RULES:
        if any(w in category for w in words):
            return label, rid
    return "기타", "R00"


def name_hint(name):
    up = str(name).upper() + " "
    hits = [lab for lab, words in NAME_HINTS.items() if any(w.upper() in up for w in words)]
    return hits


def main():
    df = pd.read_csv(os.path.join(config.DATA_PROCESSED, "places_clean.csv"), dtype={"place_id": str, "phone": str})
    res = df["category_name"].fillna("").apply(auto_label)
    df["label_auto"] = [r[0] for r in res]
    df["rule_id"] = [r[1] for r in res]
    hints = df["place_name"].apply(name_hint)
    df["name_hint"] = hints.apply(lambda h: ",".join(h))
    df["conflict"] = [bool(h) and lab not in h for h, lab in zip(hints, df["label_auto"])]
    # 신뢰도: 3단계 이상 분류로 규칙이 걸림 & 충돌 없음 → high
    df["confidence"] = "high"
    df.loc[(df["category_depth"] <= 2) | (df["rule_id"] == "R00"), "confidence"] = "low"
    df.loc[df["conflict"], "confidence"] = "low"

    os.makedirs(config.DATA_PROCESSED, exist_ok=True)
    df.to_csv(os.path.join(config.DATA_PROCESSED, "places_labeled_auto.csv"), index=False, encoding="utf-8-sig")

    # ---- 층화 표본 ----
    counts = df["label_auto"].value_counts()
    per = {}
    remain = SAMPLE_TOTAL
    for lab, n in counts.items():
        per[lab] = min(n, MIN_PER_CLASS)
        remain -= per[lab]
    rest = counts - pd.Series(per)
    if remain > 0 and rest.sum() > 0:
        extra = (rest / rest.sum() * remain).round().astype(int)
        for lab in per:
            per[lab] += int(min(extra.get(lab, 0), rest[lab]))
    parts = [df[df.label_auto == lab].sample(n=k, random_state=SEED) for lab, k in per.items() if k > 0]
    sample = pd.concat(parts).sample(frac=1, random_state=SEED).reset_index(drop=True)
    sample.insert(0, "no", range(1, len(sample) + 1))

    # ---- 엑셀 검수 시트 ----
    os.makedirs(config.DATA_LABELING, exist_ok=True)
    sheet_path = os.path.join(config.DATA_LABELING, "labeling_sheet.xlsx")
    if os.path.exists(sheet_path) and "--force" not in sys.argv:
        chk = pd.read_excel(sheet_path)
        if (chk["확인"].fillna("").astype(str).str.upper() == "O").any():
            sys.exit("[중단] 이미 검수한 labeling_sheet.xlsx 가 있어요. 덮어쓰려면 --force 를 붙이세요.")
    cols = ["no", "place_id", "place_name", "category_name", "area_type", "label_auto", "rule_id",
            "confidence", "name_hint", "label_final", "확인", "메모", "kakao_url"]
    sample["label_final"] = sample["label_auto"]
    sample["확인"] = ""
    sample["메모"] = ""
    wb = Workbook()
    ws = wb.active
    ws.title = "labeling"
    ws.append(cols)
    for row in sample[cols].itertuples(index=False):
        ws.append(list(row))
    n = len(sample) + 1
    head_fill = PatternFill("solid", fgColor="F26B3A")
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = head_fill
        c.alignment = Alignment(horizontal="center")
    widths = {"A": 6, "B": 12, "C": 26, "D": 34, "E": 9, "F": 11, "G": 7, "H": 9, "I": 12, "J": 12, "K": 6,
              "L": 20, "M": 34}
    for k, v in widths.items():
        ws.column_dimensions[k].width = v
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:M{n}"
    dv = DataValidation(type="list", formula1='"' + ",".join(config.LABELS + [config.EXCLUDE]) + '"',
                        allow_blank=False, showErrorMessage=True, error="목록에서 고르세요")
    dv.add(f"J2:J{n}")
    ok = DataValidation(type="list", formula1='"O"', allow_blank=True)
    ok.add(f"K2:K{n}")
    ws.add_data_validation(dv)
    ws.add_data_validation(ok)
    low_fill = PatternFill("solid", fgColor="FFF2CC")
    for r in range(2, n + 1):
        cell = ws.cell(r, 13)
        cell.hyperlink = cell.value
        cell.font = Font(color="0563C1", underline="single")
        if ws.cell(r, 8).value == "low":
            for c in range(1, 14):
                if c != 13:
                    ws.cell(r, c).fill = low_fill
        ws.cell(r, 10).fill = PatternFill("solid", fgColor="E2EFDA")

    g = wb.create_sheet("라벨 정의")
    g.append(["라벨", "정의", "예시"])
    for lab, d, e in GUIDE:
        g.append([lab, d, e])
    g.column_dimensions["A"].width = 12
    g.column_dimensions["B"].width = 60
    g.column_dimensions["C"].width = 40
    for c in g[1]:
        c.font = Font(bold=True)

    out = os.path.join(config.DATA_LABELING, "labeling_sheet.xlsx")
    wb.save(out)

    stats = {
        "total": len(df),
        "label_auto_counts": counts.to_dict(),
        "label_auto_pct": (counts / len(df) * 100).round(1).to_dict(),
        "rule_counts": df["rule_id"].value_counts().sort_index().to_dict(),
        "low_confidence_pct": round(float((df["confidence"] == "low").mean() * 100), 1),
        "conflict_pct": round(float(df["conflict"].mean() * 100), 1),
        "by_area_type": (pd.crosstab(df["label_auto"], df["area_type"], normalize="columns") * 100).round(1).to_dict(),
        "by_area_type_count": pd.crosstab(df["label_auto"], df["area_type"]).to_dict(),
        "sample_size": len(sample),
        "sample_per_label": sample["label_auto"].value_counts().to_dict(),
    }
    with open(os.path.join(config.REPORTS, "step4_label.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)

    print(f"자동 라벨 {len(df):,}건 → data/processed/places_labeled_auto.csv")
    for lab, k in counts.items():
        print(f"  {lab:<8} {k:>7,}건 ({k / len(df) * 100:.1f}%)")
    print(f"  '기타'(규칙 미해당) {stats['label_auto_pct'].get('기타', 0)}% / 신뢰도 낮음 {stats['low_confidence_pct']}%")
    print(f"\n검수 시트 {len(sample):,}건 → {out}")
    print("  엑셀에서 label_final 을 확인·수정하고 '확인' 칸에 O 를 입력하세요. (노란 줄 = 먼저 볼 것)")


GUIDE = [
    ("한식", "밥·국·찌개·고기구이·국밥·냉면·횟집 등 한국 음식 위주 식당", "김치찌개집, 삼겹살집, 국밥, 횟집, 백반"),
    ("분식", "김밥·떡볶이·라면·토스트·도시락 등 간단하고 저렴한 한 끼", "김밥천국, 엽기떡볶이, 이삭토스트, 한솥"),
    ("중식", "짜장면·짬뽕·탕수육·마라탕·양꼬치 등 중국 음식", "OO반점, 마라탕, 양꼬치"),
    ("일식", "초밥·라멘·돈까스·우동·덮밥 등 일본 음식 (식사 위주)", "스시, 라멘집, 돈까스 전문점"),
    ("양식", "파스타·피자·햄버거·스테이크·브런치 등 서양 음식", "맘스터치, 피자집, 파스타집"),
    ("아시안", "베트남·태국·인도·튀르키예·몽골 등 아시아 음식 (멕시칸은 양식)", "쌀국수, 팟타이, 인도커리, 케밥"),
    ("치킨", "치킨이 주 메뉴인 가게 (포장·배달 위주 포함)", "BBQ, 교촌, 동네 통닭"),
    ("술집", "술이 주 목적인 가게. 이름에 호프·포차·주점·펍·이자카야가 있으면 술집", "치킨호프, 이자카야, 포차, 와인바"),
    ("카페·디저트", "커피·음료·빵·케이크·아이스크림 위주", "스타벅스, 동네 빵집, 탕후루"),
    ("기타", "음식점은 맞지만 위 분류에 넣기 어려운 곳 (뷔페, 샐러드 등)", "샐러드 전문점, 뷔페"),
    ("제외", "음식점이 아니거나 폐업·판단 불가", "편의점, 정육점, 반찬가게, 정보 없음"),
]

if __name__ == "__main__":
    main()
