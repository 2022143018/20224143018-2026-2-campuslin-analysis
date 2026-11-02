"""2단계: 전처리

1) 반경(1km) 밖 제거  2) 음식점·카페 외 제거  3) 이름·좌표 누락 제거
4) 같은 가게가 여러 지역에 잡힌 경우 → 가장 가까운 지역 하나만 남김
5) 일반상권 중 대학에서 1.5km 이내 가게 제거 (대학가 영향 배제)
6) 카카오 분류를 단계별(cat1~cat4)로 분리

실행: python step2_preprocess.py
결과: data/processed/places_clean.csv, reports/step2_preprocess.json
"""
import json
import math
import os

import pandas as pd

import config


def haversine_km(lat1, lng1, lat2, lng2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def main():
    raw = pd.read_csv(os.path.join(config.DATA_RAW, "places_raw.csv"), dtype={"place_id": str, "phone": str})
    with open(os.path.join(config.DATA_RAW, "areas.json"), encoding="utf-8") as f:
        areas = json.load(f)
    univs = [a for a in areas if a["area_type"] == "대학가"]
    steps = [("원본 (지역별 수집 합계)", len(raw))]

    df = raw[raw["dist_km"] <= config.RADIUS_KM]
    steps.append((f"반경 {config.RADIUS_KM:g}km 밖 제거", len(df)))

    df = df[df["category_group_code"].isin(["FD6", "CE7"])]
    steps.append(("음식점·카페 외 제거", len(df)))

    df = df.dropna(subset=["place_name", "x", "y", "category_name"])
    df = df[df["place_name"].str.strip() != ""]
    steps.append(("이름·좌표·분류 누락 제거", len(df)))

    df = df.sort_values("dist_km").drop_duplicates("place_id", keep="first")
    steps.append(("중복 가게 제거 (가장 가까운 지역 1곳만)", len(df)))

    def near_univ(row):
        return min(haversine_km(row["y"], row["x"], u["lat"], u["lng"]) for u in univs) <= config.CONTROL_EXCLUDE_KM
    is_control = df["area_type"] == "일반상권"
    drop = df[is_control].apply(near_univ, axis=1) if is_control.any() else pd.Series(dtype=bool)
    df = df.drop(drop[drop].index)
    steps.append((f"일반상권 중 대학 {config.CONTROL_EXCLUDE_KM:g}km 이내 제거", len(df)))

    cats = df["category_name"].str.split(" > ", expand=True).reindex(columns=range(4))
    df["cat1"], df["cat2"], df["cat3"], df["cat4"] = cats[0], cats[1], cats[2], cats[3]
    df["category_depth"] = df["category_name"].str.count(" > ") + 1
    df["kakao_url"] = "https://place.map.kakao.com/" + df["place_id"]
    df = df.sort_values(["area_type", "area_name", "place_name"]).reset_index(drop=True)

    os.makedirs(config.DATA_PROCESSED, exist_ok=True)
    os.makedirs(config.REPORTS, exist_ok=True)
    out = os.path.join(config.DATA_PROCESSED, "places_clean.csv")
    df.to_csv(out, index=False, encoding="utf-8-sig")

    result = {
        "steps": steps,
        "final": len(df),
        "by_area_type": df["area_type"].value_counts().to_dict(),
        "areas": {t: int((pd.DataFrame(areas)["area_type"] == t).sum()) for t in ["대학가", "일반상권"]},
    }
    with open(os.path.join(config.REPORTS, "step2_preprocess.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    for name, n in steps:
        print(f"  {name:<40} {n:>8,}건")
    print(f"\n전처리 후 {len(df):,}건 → {out}")
    if len(df) < 25000:
        print("  ⚠ 25,000건 미만이에요. config.py 의 대학·상권 목록을 늘리거나 RADIUS_KM 을 1.5로 늘려 보세요.")


if __name__ == "__main__":
    main()
