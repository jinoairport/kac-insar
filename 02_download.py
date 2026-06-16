# -*- coding: utf-8 -*-
"""
[2단계] HyP3 처리 완료된 간섭도 산출물 다운로드 + 압축 해제
실행:  python 02_download.py
재실행 시 이미 받은 파일은 건너뜀.
"""
import zipfile
from pathlib import Path

from hyp3_sdk import HyP3

from airports import select_airport

airport = select_airport()
print(f"\n[선택] {airport['name']} ({airport['code']})")

OUT = Path("hyp3_products") / airport["code"]
OUT.mkdir(parents=True, exist_ok=True)

hyp3 = HyP3()

# 새 이름으로 먼저 찾고, 없으면 이전 이름(GMH-SBAS)도 확인
PROJECT = f"KAC-SBAS-{airport['code']}"
batch = hyp3.find_jobs(name=PROJECT)
if not batch and airport["code"] == "PUS":
    PROJECT = "GMH-SBAS"
    batch = hyp3.find_jobs(name=PROJECT)
if not batch:
    raise SystemExit("해당 공항의 작업이 없습니다. 01번 스크립트를 먼저 실행하세요.")

n_run  = sum(1 for j in batch if j.running() or j.pending())
n_fail = sum(1 for j in batch if j.failed())
n_ok   = sum(1 for j in batch if j.succeeded())
print(f"[현황] 완료 {n_ok} / 처리중 {n_run} / 실패 {n_fail}")
if n_run:
    print("→ 아직 처리 중인 작업이 있습니다. 완료분만 먼저 받습니다. 나중에 재실행하면 나머지를 이어받습니다.")

for job in batch:
    if not job.succeeded():
        continue
    fname  = job.to_dict()["files"][0]["filename"]
    fsize  = job.to_dict()["files"][0]["size"]   # 서버측 파일 크기(bytes)
    zpath  = OUT / fname
    exdir  = OUT / fname.replace(".zip", "")

    if exdir.exists():
        continue  # 이미 압축 해제 완료

    # 부분 다운로드 감지: 크기가 다르면 삭제 후 재시도
    if zpath.exists() and zpath.stat().st_size != fsize:
        print(f"[불완전] {fname} ({zpath.stat().st_size//1024//1024}MB / {fsize//1024//1024}MB) → 재다운로드")
        zpath.unlink()

    if not zpath.exists():
        print(f"[다운로드] {fname}")
        job.download_files(OUT)

    print(f"[해제] {fname}")
    with zipfile.ZipFile(zpath) as z:
        z.extractall(OUT)
    zpath.unlink()

print(f"\n완료. 다음으로 03_clip_and_run.py 를 실행하세요. (공항: {airport['name']})")
