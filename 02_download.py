# -*- coding: utf-8 -*-
"""
[2단계] HyP3 처리 완료된 간섭도 산출물 다운로드 + 압축 해제
실행:  python 02_download.py [공항번호 [해상도m]]
  예)  python 02_download.py 3 40   ← PUS(김해) INT40 다운로드
      python 02_download.py 3       ← PUS(김해) INT80 (기본)
재실행 시 이미 받은 파일은 건너뜀.
"""
import sys
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hyp3_sdk import HyP3
from tqdm import tqdm

from airports import select_airport, AIRPORTS

CHUNK    = 1024 * 1024   # 1 MB
TIMEOUT  = 60            # 60초 이상 데이터 없으면 타임아웃
MAX_RETRY = 5


def get_airport():
    if len(sys.argv) > 1:
        try:
            sel = int(sys.argv[1])
            if 1 <= sel <= len(AIRPORTS):
                return AIRPORTS[sel - 1]
        except ValueError:
            pass
    return select_airport()


def download_with_timeout(session, get_url, dest, expected_size):
    """타임아웃 + 자동 재시도 다운로드. get_url()로 매 시도마다 최신 URL 취득."""
    for attempt in range(1, MAX_RETRY + 1):
        url = get_url()
        if not url:
            print(f"  [실패] URL을 가져올 수 없습니다.")
            return False
        try:
            if dest.exists():
                dest.unlink()
            with session.get(url, stream=True, timeout=(30, TIMEOUT)) as r:
                r.raise_for_status()
                with open(dest, "wb") as f, tqdm(
                    total=expected_size, unit="B", unit_scale=True,
                    unit_divisor=1024, leave=True
                ) as bar:
                    for chunk in r.iter_content(chunk_size=CHUNK):
                        f.write(chunk)
                        bar.update(len(chunk))
            return True
        except Exception as e:
            status = getattr(getattr(e, 'response', None), 'status_code', '')
            tag = f" HTTP {status}" if status else ""
            if dest.exists():
                dest.unlink()
            if attempt < MAX_RETRY:
                wait = 30 * attempt
                print(f"  [재시도 {attempt}/{MAX_RETRY}] {type(e).__name__}{tag} → URL 갱신 후 {wait}초 대기...")
                time.sleep(wait)
            else:
                print(f"  [실패] {type(e).__name__}{tag} — {MAX_RETRY}회 시도 후 실패. 건너뜁니다.")
    return False


airport = get_airport()
code    = airport["code"]
print(f"\n[선택] {airport['name']} ({code})")

try:
    RES = int(sys.argv[2]) if len(sys.argv) > 2 else 80
except ValueError:
    RES = 80
D_SUFFIX = f"_INT{RES}" if RES != 80 else ""
P_SUFFIX = f"-INT{RES}" if RES != 80 else ""

OUT     = Path("hyp3_products") / (code + D_SUFFIX)
PROJECT = f"KAC-SBAS-{code}{P_SUFFIX}"
OUT.mkdir(parents=True, exist_ok=True)
print(f"[프로젝트] {PROJECT}  다운로드 위치: {OUT}")

hyp3  = HyP3()
cutoff = datetime.now(timezone.utc) - timedelta(days=14)
batch = [
    j for j in hyp3.find_jobs(name=PROJECT)
    if datetime.fromisoformat(
        j.to_dict().get("request_time", "2000-01-01T00:00:00Z").replace("Z", "+00:00")
    ) > cutoff
]
if not batch and RES == 80 and code == "PUS":
    PROJECT = "GMH-SBAS"
    batch = hyp3.find_jobs(name=PROJECT)
if not batch:
    raise SystemExit("해당 공항의 작업이 없습니다. 01번 스크립트를 먼저 실행하세요.")

n_run  = sum(1 for j in batch if j.running() or j.pending())
n_fail = sum(1 for j in batch if j.failed())
n_ok   = sum(1 for j in batch if j.succeeded())
print(f"[현황] 완료 {n_ok} / 처리중 {n_run} / 실패 {n_fail}")
if n_run:
    print("→ 아직 처리 중인 작업이 있습니다. 완료분만 먼저 받습니다.")

for job in batch:
    if not job.succeeded():
        continue
    fname  = job.to_dict()["files"][0]["filename"]
    fsize  = job.to_dict()["files"][0]["size"]
    zpath  = OUT / fname
    exdir  = OUT / fname.replace(".zip", "")

    if exdir.exists():
        continue

    if zpath.exists() and zpath.stat().st_size != fsize:
        print(f"[불완전] {fname} ({zpath.stat().st_size//1024//1024}MB / {fsize//1024//1024}MB) → 재다운로드")
        zpath.unlink()

    if not zpath.exists():
        print(f"[다운로드] {fname}  ({fsize//1024//1024}MB)")
        job_id = job.job_id
        def make_get_url(jid):
            def _get():
                fresh = hyp3.find_jobs(name=PROJECT)
                j = next((x for x in fresh if x.job_id == jid), None)
                return j.to_dict()["files"][0]["url"] if j else None
            return _get
        if not download_with_timeout(hyp3.session, make_get_url(job_id), zpath, fsize):
            continue

    if not zpath.exists():
        continue

    print(f"[해제] {fname}")
    with zipfile.ZipFile(zpath) as z:
        z.extractall(OUT)
    zpath.unlink()

print(f"\n완료. 다음으로 03_clip_and_run.py 를 실행하세요. (공항: {airport['name']})")
