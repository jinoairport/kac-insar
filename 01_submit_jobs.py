# -*- coding: utf-8 -*-
"""
[1단계] 공항 선택 → Sentinel-1 영상 검색 → ASF HyP3 클라우드에 InSAR 처리 요청
실행:  python 01_submit_jobs.py [공항번호 [해상도m]]
  예)  python 01_submit_jobs.py 3 20   ← PUS(김해) INT20 제출
      python 01_submit_jobs.py 3       ← PUS(김해) INT80 (기본)
처리는 ASF 서버에서 진행되며 보통 수 시간 소요. 완료 후 02번 스크립트 실행.
"""
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import asf_search as asf
from hyp3_sdk import HyP3

from airports import select_airport, AIRPORTS


def get_airport():
    if len(sys.argv) > 1:
        try:
            sel = int(sys.argv[1])
            if 1 <= sel <= len(AIRPORTS):
                return AIRPORTS[sel - 1]
        except ValueError:
            pass
    return select_airport()


airport = get_airport()
print(f"\n[선택] {airport['name']} ({airport['code']})  좌표: {airport['lon']}, {airport['lat']}")

# ─────────── 해상도 설정 ───────────
try:
    RES = int(sys.argv[2]) if len(sys.argv) > 2 else 80
except ValueError:
    RES = 80
LOOKS_MAP = {80: "20x4", 40: "10x2"}
LOOKS     = LOOKS_MAP.get(RES, "20x4")
P_SUFFIX  = f"-INT{RES}" if RES != 80 else ""

# ─────────── 설정 ───────────
PROJECT   = f"KAC-SBAS-{airport['code']}{P_SUFFIX}"
AOI       = f"POINT({airport['lon']} {airport['lat']})"
START     = "2024-06-01"
THIN_DAYS = 24
MAX_PAIRS_PER_SCENE = 2
# ────────────────────────────

print(f"[프로젝트] {PROJECT}  해상도: {RES}m  (looks={LOOKS})")
print(f"[검색] {START} 이후 Sentinel-1 SLC, AOI={AOI}")
results = asf.geo_search(
    intersectsWith=AOI,
    platform=asf.PLATFORM.SENTINEL1,
    processingLevel=asf.PRODUCT_TYPE.SLC,
    beamMode="IW",
    start=START,
)
if not results:
    sys.exit("검색 결과가 없습니다. AOI/날짜를 확인하세요.")

by_path = defaultdict(list)
for r in results:
    by_path[r.properties["pathNumber"]].append(r)
path = max(by_path, key=lambda k: len(by_path[k]))
scenes = sorted(by_path[path], key=lambda r: r.properties["startTime"])
print(f"[궤도] path {path} 선택 (영상 {len(scenes)}장 / 전체 {len(results)}장)")

picked, last = [], None
for r in scenes:
    t = datetime.fromisoformat(r.properties["startTime"].replace("Z", "+00:00"))
    if last is None or (t - last).days >= THIN_DAYS:
        picked.append(r)
        last = t
names = [r.properties["sceneName"] for r in picked]
print(f"[선별] {THIN_DAYS}일 간격 적용 → {len(names)}장 사용")

pairs = [(names[i], names[j])
         for i in range(len(names))
         for j in range(i + 1, min(i + 1 + MAX_PAIRS_PER_SCENE, len(names)))]
print(f"[페어] 간섭쌍 {len(pairs)}개 구성")

FORCE = "--force" in sys.argv

hyp3 = HyP3()
done = set()
if not FORCE:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    for job in hyp3.find_jobs(name=PROJECT):
        d = job.to_dict()
        rt = d.get("request_time", "")
        if rt:
            jt = datetime.fromisoformat(rt.replace("Z", "+00:00"))
            if jt < cutoff:
                continue  # 7일 이전 잡은 파일 만료 → 재제출 대상
        g = d.get("job_parameters", {}).get("granules", [])
        if len(g) == 2:
            done.add((g[0], g[1]))
todo = [p for p in pairs if p not in done]
if FORCE:
    print(f"[제출] 강제 재제출 {len(todo)}개 (--force 옵션)")
else:
    print(f"[제출] 신규 {len(todo)}개 (기존 제출 {len(done)}개 제외)")

for i, (ref, sec) in enumerate(todo, 1):
    for attempt in range(1, 4):
        try:
            hyp3.submit_insar_job(
                ref, sec, name=PROJECT,
                looks=LOOKS,
                include_dem=True,
                include_inc_map=True,
                include_look_vectors=True,
            )
            print(f"  ({i}/{len(todo)}) {ref[17:25]} - {sec[17:25]} 제출")
            break
        except Exception as e:
            if attempt < 3:
                print(f"  ({i}/{len(todo)}) 서버 오류 → {30*attempt}초 후 재시도... ({e})")
                import time; time.sleep(30 * attempt)
            else:
                print(f"  ({i}/{len(todo)}) 실패 — 건너뜁니다: {e}")

try:
    print(f"\n[크레딧] 잔여: {hyp3.check_credits()}")
except Exception:
    pass
print(f"\n완료. 수 시간 후 02_download.py 를 실행하세요. (공항: {airport['name']})")
print("진행 상황은 search.asf.alaska.edu 로그인 → On Demand 메뉴에서도 확인 가능합니다.")
