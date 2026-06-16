# -*- coding: utf-8 -*-
# 한국공항공사 관리 공항 목록 및 선택 메뉴 (모든 스크립트 공용)

AIRPORTS = [
    {"name": "김포공항",     "code": "GMP", "lon": 126.7906, "lat": 37.5583},
    {"name": "제주공항",     "code": "CJU", "lon": 126.4930, "lat": 33.5113},
    {"name": "김해공항",     "code": "PUS", "lon": 128.9381, "lat": 35.1795},
    {"name": "대구공항",     "code": "TAE", "lon": 128.6586, "lat": 35.8971},
    {"name": "청주공항",     "code": "CJJ", "lon": 127.4991, "lat": 36.7172},
    {"name": "광주공항",     "code": "KWJ", "lon": 126.8088, "lat": 35.1264},
    {"name": "여수공항",     "code": "RSU", "lon": 127.6169, "lat": 34.8423},
    {"name": "사천공항",     "code": "HIN", "lon": 128.0703, "lat": 35.0883},
    {"name": "울산공항",     "code": "USN", "lon": 129.3522, "lat": 35.5935},
    {"name": "포항경주공항", "code": "KPO", "lon": 129.4199, "lat": 35.9879},
    {"name": "군산공항",     "code": "KUV", "lon": 126.6159, "lat": 35.9038},
    {"name": "원주공항",     "code": "WJU", "lon": 127.9596, "lat": 37.4381},
    {"name": "양양공항",     "code": "YNY", "lon": 128.6693, "lat": 38.0613},
    {"name": "무안공항",     "code": "MWX", "lon": 126.3828, "lat": 34.9914},
]

BUF = 0.04  # 공항 중심에서 ±0.04도 (약 4km) — 분석 범위


def select_airport():
    """공항 선택 메뉴를 표시하고 선택된 공항 정보를 반환."""
    print("=" * 40)
    print("  한국공항공사 지반침하 분석 시스템")
    print("=" * 40)
    for i, ap in enumerate(AIRPORTS, 1):
        print(f"  {i:2d}. {ap['name']} ({ap['code']})")
    print(f"  {len(AIRPORTS)+1:2d}. 직접 입력")
    print("=" * 40)

    while True:
        try:
            sel = int(input("공항 번호 선택 > "))
            if 1 <= sel <= len(AIRPORTS):
                return AIRPORTS[sel - 1]
            elif sel == len(AIRPORTS) + 1:
                name = input("지역 이름 입력 > ")
                lon  = float(input("경도(longitude) 입력 (예: 128.938) > "))
                lat  = float(input("위도(latitude)  입력 (예:  35.178) > "))
                return {"name": name, "code": "CUSTOM", "lon": lon, "lat": lat}
            else:
                print("올바른 번호를 입력하세요.")
        except ValueError:
            print("숫자를 입력하세요.")
