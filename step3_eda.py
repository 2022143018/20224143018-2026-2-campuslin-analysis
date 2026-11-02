"""3단계: EDA (원본 + 전처리 데이터)

실행: python step3_eda.py
결과: reports/figures/*.png, reports/step3_eda.json
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd

import config

# 한글 폰트 (윈도우: 맑은 고딕)
for name in ["Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR"]:
    if any(name == f.name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = name
        break
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 110
C_UNIV, C_CTRL, C_GRAY = "#F26B3A", "#3A7BD5", "#9AA4B1"


def save(fig, name):
    os.makedirs(config.FIGURES, exist_ok=True)
    fig.tight_layout()
    fig.savefig(os.path.join(config.FIGURES, name), bbox_inches="tight")
    plt.close(fig)
    return f"reports/figures/{name}"


def main():
    raw = pd.read_csv(os.path.join(config.DATA_RAW, "places_raw.csv"), dtype={"place_id": str, "phone": str})
    df = pd.read_csv(os.path.join(config.DATA_PROCESSED, "places_clean.csv"), dtype={"place_id": str, "phone": str})
    figs, r = {}, {}

    # ---- 원본 데이터 개요 ----
    r["raw_rows"] = len(raw)
    r["raw_cols"] = list(raw.columns)
    r["raw_unique_places"] = int(raw["place_id"].nunique())
    r["raw_dup_rows"] = int(len(raw) - raw["place_id"].nunique())
    r["raw_missing"] = {c: round(float(raw[c].isna().mean() * 100), 1) for c in raw.columns
                        if raw[c].isna().any() or (raw[c].astype(str).str.strip() == "").any()}
    r["raw_blank"] = {c: round(float((raw[c].fillna("").astype(str).str.strip() == "").mean() * 100), 1)
                      for c in ["phone", "road_address_name", "category_name"]}
    r["raw_group"] = raw["category_group_code"].value_counts().to_dict()

    # ---- 원본(전처리 전) 기준 그래프 ----
    # R1. 중심으로부터 거리: 사각형으로 수집했기 때문에 반경 밖 데이터가 섞여 있음
    out_pct = float((raw["dist_km"] > config.RADIUS_KM).mean() * 100)
    r["raw_out_of_radius_pct"] = round(out_pct, 1)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(raw["dist_km"], bins=40, color=C_GRAY)
    ax.axvline(config.RADIUS_KM, color=C_UNIV, ls="--", lw=2)
    ax.text(config.RADIUS_KM + 0.02, ax.get_ylim()[1] * .9, f"반경 {config.RADIUS_KM:g}km\n밖: {out_pct:.1f}%",
            color=C_UNIV)
    ax.set_title("[원본] 지역 중심으로부터 거리 분포")
    ax.set_xlabel("거리 (km)")
    ax.set_ylabel("행 수")
    figs["raw_dist"] = save(fig, "00a_raw_distance.png")

    # R2. 같은 가게가 몇 개 지역에서 중복 수집됐는지
    times = raw.groupby("place_id").size().clip(upper=5)
    vc = times.value_counts().sort_index()
    r["raw_place_area_count"] = {("5+" if k == 5 else str(k)): int(v) for k, v in vc.items()}
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(["5+" if k == 5 else str(k) for k in vc.index], vc.values, color=C_CTRL)
    for i, v in enumerate(vc.values):
        ax.text(i, v, f"{v:,}", ha="center", va="bottom", fontsize=9)
    ax.set_title("[원본] 한 가게가 수집된 지역 수 (중복)")
    ax.set_xlabel("수집된 지역 수")
    ax.set_ylabel("가게 수")
    figs["raw_dup"] = save(fig, "00b_raw_duplicates.png")

    # R3. 카카오 분류 깊이 + 그룹(음식점/카페)
    raw_depth = raw["category_name"].fillna("").str.count(" > ") + 1
    r["raw_depth_counts"] = raw_depth.value_counts().sort_index().to_dict()
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    dc = raw_depth.value_counts().sort_index()
    axes[0].bar(dc.index.astype(str), dc.values, color=C_GRAY)
    axes[0].set_title("[원본] 카카오 분류 깊이 (단계 수)")
    axes[0].set_xlabel("단계")
    gc = raw["category_group_code"].map({"FD6": "음식점(FD6)", "CE7": "카페(CE7)"}).fillna("기타").value_counts()
    axes[1].bar(gc.index, gc.values, color=[C_UNIV, C_CTRL, C_GRAY][:len(gc)])
    axes[1].set_title("[원본] 카카오 그룹 코드")
    figs["raw_depth"] = save(fig, "00c_raw_category_depth.png")

    # ---- 지역별 가게 수 ----
    per_area = df.groupby(["area_type", "area_name"]).size().rename("n").reset_index()
    r["per_area"] = per_area.groupby("area_type")["n"].describe().round(1).to_dict(orient="index")
    top = per_area.sort_values("n", ascending=False).head(15)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(top["area_name"][::-1], top["n"][::-1],
            color=[C_UNIV if t == "대학가" else C_CTRL for t in top["area_type"][::-1]])
    ax.set_title("지역별 가게 수 TOP 15 (반경 1km, 전처리 후)")
    ax.set_xlabel("가게 수")
    figs["per_area"] = save(fig, "01_per_area_top15.png")

    fig, ax = plt.subplots(figsize=(7, 4))
    for t, c in [("대학가", C_UNIV), ("일반상권", C_CTRL)]:
        ax.hist(per_area[per_area.area_type == t]["n"], bins=15, alpha=.7, color=c, label=t)
    ax.set_title("지역당 가게 수 분포")
    ax.set_xlabel("지역당 가게 수")
    ax.set_ylabel("지역 수")
    ax.legend()
    figs["per_area_hist"] = save(fig, "02_per_area_hist.png")

    # ---- 카카오 분류 계층 ----
    r["depth_counts"] = df["category_depth"].value_counts().sort_index().to_dict()
    r["cat2_n_unique"] = int(df["cat2"].nunique())
    r["cat3_n_unique"] = int(df["cat3"].nunique())
    top_cat2 = df["cat2"].fillna("(없음)").value_counts().head(20)
    r["top_cat2"] = top_cat2.to_dict()
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(top_cat2.index[::-1], top_cat2.values[::-1], color=C_GRAY)
    ax.set_title("카카오 2단계 분류 TOP 20")
    ax.set_xlabel("가게 수")
    figs["top_cat2"] = save(fig, "03_kakao_cat2_top20.png")

    # 2단계 분류가 '음식점'/'카페' 수준에서 끝나 정보가 부족한 비율
    r["shallow_pct"] = round(float((df["category_depth"] <= 2).mean() * 100), 1)

    # ---- 대학가 vs 일반상권 업종 구성 (카카오 2단계 기준) ----
    comp = (pd.crosstab(df["cat2"].fillna("(없음)"), df["area_type"], normalize="columns") * 100).round(1)
    keep = df["cat2"].fillna("(없음)").value_counts().head(10).index
    comp = comp.loc[keep]
    r["composition_cat2"] = comp.to_dict()
    fig, ax = plt.subplots(figsize=(9, 5))
    x = range(len(comp))
    w = .4
    if "대학가" in comp:
        ax.bar([i - w / 2 for i in x], comp["대학가"], w, label="대학가", color=C_UNIV)
    if "일반상권" in comp:
        ax.bar([i + w / 2 for i in x], comp["일반상권"], w, label="일반상권", color=C_CTRL)
    ax.set_xticks(list(x))
    ax.set_xticklabels(comp.index, rotation=30, ha="right")
    ax.set_ylabel("비율 (%)")
    ax.set_title("대학가 vs 일반상권 업종 구성 (카카오 2단계 분류 상위 10)")
    ax.legend()
    figs["composition"] = save(fig, "04_univ_vs_control_cat2.png")

    # ---- 가게 이름 길이 / 거리 분포 ----
    name_len = df["place_name"].str.len()
    r["name_len"] = name_len.describe().round(1).to_dict()
    r["dist_km"] = df["dist_km"].describe().round(3).to_dict()
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    axes[0].hist(name_len, bins=30, color=C_GRAY)
    axes[0].set_title("가게 이름 길이 (글자 수)")
    axes[1].hist(df["dist_km"], bins=30, color=C_GRAY)
    axes[1].set_title("지역 중심으로부터 거리 (km)")
    figs["dist"] = save(fig, "05_name_len_and_distance.png")

    r["figures"] = figs
    with open(os.path.join(config.REPORTS, "step3_eda.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=1, default=str)
    print(f"EDA 완료: 그림 {len(figs)}개 → reports/figures/")
    print(f"  원본 {r['raw_rows']:,}행 / 고유 가게 {r['raw_unique_places']:,} / 중복 {r['raw_dup_rows']:,}")
    print(f"  카카오 분류가 2단계 이하로 얕은 가게: {r['shallow_pct']}%")


if __name__ == "__main__":
    main()
