# -*- coding: utf-8 -*-
"""
자동 업데이트 스크립트 — 매월 Windows 작업 스케줄러로 실행
사용법:  python auto_update.py PUS
         python auto_update.py PUS GMP CJU   (여러 공항 순서대로)
"""
import sys
import time
import zipfile
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

from hyp3_sdk import HyP3
import asf_search as asf
from collections import defaultdict

from airports import AIRPORTS, BUF

LOG = Path("auto_update.log")

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def get_airport(code):
    ap = next((a for a in AIRPORTS if a["code"] == code), None)
    if not ap:
        log(f"[오류] 알 수 없는 공항 코드: {code}")
        log(f"       사용 가능 코드: {', '.join(a['code'] for a in AIRPORTS)}")
        sys.exit(1)
    return ap

def step1_submit(hyp3, airport):
    PROJECT = f"KAC-SBAS-{airport['code']}"
    AOI = f"POINT({airport['lon']} {airport['lat']})"
    START = "2024-06-01"
    THIN_DAYS = 24
    MAX_PAIRS = 2

    log(f"[1단계] {airport['name']} 영상 검색 중...")
    results = asf.geo_search(
        intersectsWith=AOI, platform=asf.PLATFORM.SENTINEL1,
        processingLevel=asf.PRODUCT_TYPE.SLC, beamMode="IW", start=START,
    )
    if not results:
        log("검색 결과 없음. 건너뜀.")
        return 0

    by_path = defaultdict(list)
    for r in results:
        by_path[r.properties["pathNumber"]].append(r)
    path = max(by_path, key=lambda k: len(by_path[k]))
    scenes = sorted(by_path[path], key=lambda r: r.properties["startTime"])

    from datetime import datetime as dt
    picked, last = [], None
    for r in scenes:
        t = dt.fromisoformat(r.properties["startTime"].replace("Z", "+00:00"))
        if last is None or (t - last).days >= THIN_DAYS:
            picked.append(r); last = t
    names = [r.properties["sceneName"] for r in picked]

    pairs = [(names[i], names[j])
             for i in range(len(names))
             for j in range(i+1, min(i+1+MAX_PAIRS, len(names)))]

    done = set()
    for job in hyp3.find_jobs(name=PROJECT):
        g = job.to_dict().get("job_parameters", {}).get("granules", [])
        if len(g) == 2: done.add((g[0], g[1]))
    todo = [p for p in pairs if p not in done]

    log(f"[1단계] 신규 {len(todo)}개 제출 (기존 {len(done)}개 제외)")
    for ref, sec in todo:
        hyp3.submit_insar_job(ref, sec, name=PROJECT, looks="20x4",
                              include_dem=True, include_inc_map=True, include_look_vectors=True)
    return len(todo)

def step2_wait_and_download(hyp3, airport):
    PROJECT = f"KAC-SBAS-{airport['code']}"
    OUT = Path("hyp3_products") / airport["code"]
    OUT.mkdir(parents=True, exist_ok=True)

    log(f"[2단계] HyP3 처리 완료 대기 중...")
    while True:
        batch = hyp3.find_jobs(name=PROJECT)
        n_run = sum(1 for j in batch if j.running() or j.pending())
        n_ok  = sum(1 for j in batch if j.succeeded())
        log(f"        완료 {n_ok} / 처리중 {n_run}")
        if n_run == 0:
            break
        time.sleep(300)  # 5분마다 확인

    log(f"[2단계] 다운로드 시작...")
    for job in hyp3.find_jobs(name=PROJECT):
        if not job.succeeded(): continue
        fname = job.to_dict()["files"][0]["filename"]
        zpath = OUT / fname
        if (OUT / fname.replace(".zip", "")).exists(): continue
        if not zpath.exists():
            log(f"  다운로드: {fname}")
            job.download_files(OUT)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(OUT)
        zpath.unlink()
    log(f"[2단계] 다운로드 완료")

def step3_analyze(airport):
    log(f"[3단계] MintPy 분석 시작...")
    r = subprocess.run(
        [sys.executable, "03_clip_and_run.py"],
        input=f"{AIRPORTS.index(airport)+1}\n",
        text=True, encoding="utf-8"
    )
    if r.returncode != 0:
        log("[오류] 03번 스크립트 실패. 로그 확인 필요.")
        sys.exit(1)
    log(f"[3단계] 분석 완료")

def step4_export(airport):
    log(f"[4단계] 웹 데이터 추출 중...")
    r = subprocess.run(
        [sys.executable, "04_export_web.py"],
        input=f"{AIRPORTS.index(airport)+1}\n",
        text=True, encoding="utf-8"
    )
    if r.returncode != 0:
        log("[오류] 04번 스크립트 실패.")
        sys.exit(1)
    log(f"[4단계] 완료 — data_{airport['code']}.js 생성됨")

def cleanup(airport):
    for folder in [Path("hyp3_products") / airport["code"],
                   Path("clipped") / airport["code"]]:
        if folder.exists():
            shutil.rmtree(folder)
            log(f"[정리] {folder} 삭제 완료")

# ── 메인 ──────────────────────────────────────────────────
if len(sys.argv) < 2:
    print("사용법: python auto_update.py [공항코드] [공항코드2] ...")
    print(f"예시:   python auto_update.py PUS")
    print(f"        python auto_update.py PUS GMP CJU")
    print(f"가능한 코드: {', '.join(a['code'] for a in AIRPORTS)}")
    sys.exit(0)

codes = [c.upper() for c in sys.argv[1:]]
log(f"=== 자동 업데이트 시작: {', '.join(codes)} ===")

hyp3 = HyP3()

for code in codes:
    airport = get_airport(code)
    log(f"--- {airport['name']} ({code}) 시작 ---")
    new_jobs = step1_submit(hyp3, airport)
    step2_wait_and_download(hyp3, airport)
    step3_analyze(airport)
    step4_export(airport)
    cleanup(airport)
    log(f"--- {airport['name']} 완료 ---")

log(f"=== 전체 완료 ===")
