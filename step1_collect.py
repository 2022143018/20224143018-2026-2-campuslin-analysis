"""1단계: 데이터 수집 (카카오 로컬 API, 공식)

대학가 + 비교 상권 반경 1km의 음식점(FD6)·카페(CE7)를 모두 수집해
data/raw/places_raw.csv 로 저장합니다. (중복·정제는 2단계에서)

실행: python step1_collect.py
"""
import csv
import json
import math
import os
import sys
import time
from datetime import datetime

import requests

import config

API = "https://dapi.kakao.com/v2/local/search"
MAX_PAGEABLE = 45


def get(session, path, params):
    for attempt in range(3):
        r = session.get(f"{API}/{path}.json", params=params, timeout=10)
        if r.status_code == 429:
            time.sleep(2 + attempt)
            continue
        if r.status_code != 200:
            raise RuntimeError(f"카카오 API 오류 {r.status_code}: {r.text[:200]}")
        time.sleep(0.05)
        return r.json()
    raise RuntimeError("카카오 API 호출 제한. 잠시 후 다시 실행하세요.")


def locate(session, query, group):
    """이름으로 중심 좌표 찾기 (대학: SC4 학교, 역: SW8 지하철역)"""
    docs = get(session, "keyword", {"query": query, "category_group_code": group, "size": 5})["documents"]
    key = query.split()[0]
    docs = [d for d in docs if key in d["place_name"]] or docs
    if not docs:
        return None
    d = docs[0]
    return {"name": query, "matched": d["place_name"], "lat": float(d["y"]), "lng": float(d["x"])}


def search_rect(session, code, rect, found, depth=0):
    """사각형 검색. 45개를 넘으면 4등분해서 빠짐없이 수집"""
    x1, y1, x2, y2 = rect
    params = {"category_group_code": code, "rect": f"{x1},{y1},{x2},{y2}", "size": 15, "page": 1}
    data = get(session, "category", params)
    if data["meta"]["total_count"] > MAX_PAGEABLE and depth < 7:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        for sub in [(x1, y1, mx, my), (mx, y1, x2, my), (x1, my, mx, y2), (mx, my, x2, y2)]:
            search_rect(session, code, sub, found, depth + 1)
        return
    page = 1
    while True:
        for d in data["documents"]:
            found[d["id"]] = d
        if data["meta"]["is_end"] or page >= 3:
            break
        page += 1
        params["page"] = page
        data = get(session, "category", params)


def haversine_km(a_lat, a_lng, b_lat, b_lng):
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lng - a_lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def collect_area(session, center):
    dlat = config.RADIUS_KM / 111.0
    dlng = config.RADIUS_KM / (111.0 * math.cos(math.radians(center["lat"])))
    rect = (center["lng"] - dlng, center["lat"] - dlat, center["lng"] + dlng, center["lat"] + dlat)
    found = {}
    for code in ("FD6", "CE7"):
        search_rect(session, code, rect, found)
    return found


def main():
    key = os.getenv("KAKAO_REST_KEY")
    if not key:
        sys.exit("[오류] KAKAO_REST_KEY가 없어요. ../campuslin/.env 를 확인하세요.")
    os.makedirs(config.DATA_RAW, exist_ok=True)
    s = requests.Session()
    s.headers["Authorization"] = f"KakaoAK {key}"

    areas = []
    for q in config.UNIVERSITIES:
        c = locate(s, q, "SC4")
        print(("  ✓ " if c else "  ✗ 좌표 못 찾음: ") + q + (f" → {c['matched']}" if c else ""))
        if c:
            areas.append({**c, "area_type": "대학가"})
    for q in config.CONTROL_AREAS:
        c = locate(s, q, "SW8")
        print(("  ✓ " if c else "  ✗ 좌표 못 찾음: ") + q + (f" → {c['matched']}" if c else ""))
        if c:
            areas.append({**c, "area_type": "일반상권"})

    out = os.path.join(config.DATA_RAW, "places_raw.csv")
    fields = ["area_name", "area_type", "area_lat", "area_lng", "place_id", "place_name", "category_name",
              "category_group_code", "address_name", "road_address_name", "phone", "x", "y", "dist_km",
              "collected_at"]
    total = 0
    now = datetime.now().isoformat(timespec="seconds")
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i, a in enumerate(areas, 1):
            found = collect_area(s, a)
            for d in found.values():
                w.writerow({
                    "area_name": a["name"], "area_type": a["area_type"], "area_lat": a["lat"], "area_lng": a["lng"],
                    "place_id": d["id"], "place_name": d["place_name"], "category_name": d.get("category_name", ""),
                    "category_group_code": d.get("category_group_code", ""),
                    "address_name": d.get("address_name", ""), "road_address_name": d.get("road_address_name", ""),
                    "phone": d.get("phone", ""), "x": d["x"], "y": d["y"],
                    "dist_km": round(haversine_km(a["lat"], a["lng"], float(d["y"]), float(d["x"])), 4),
                    "collected_at": now,
                })
            total += len(found)
            print(f"[{i}/{len(areas)}] {a['area_type']} {a['name']}: {len(found)}건 (누적 {total})", flush=True)

    with open(os.path.join(config.DATA_RAW, "areas.json"), "w", encoding="utf-8") as f:
        json.dump(areas, f, ensure_ascii=False, indent=1)
    print(f"\n완료: 원본 {total}건 → {out}")


if __name__ == "__main__":
    main()
