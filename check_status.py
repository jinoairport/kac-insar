# -*- coding: utf-8 -*-
from hyp3_sdk import HyP3
from airports import select_airport

airport = select_airport()
hyp3 = HyP3()

# 새 이름으로 먼저 찾고, 없으면 이전 이름(GMH-SBAS)도 확인
PROJECT = f"KAC-SBAS-{airport['code']}"
jobs = hyp3.find_jobs(name=PROJECT)
if not jobs and airport["code"] == "PUS":
    PROJECT = "GMH-SBAS"
    jobs = hyp3.find_jobs(name=PROJECT)

n_ok   = sum(1 for j in jobs if j.succeeded())
n_run  = sum(1 for j in jobs if j.running() or j.pending())
n_fail = sum(1 for j in jobs if j.failed())

print(f"\n[{airport['name']}] 처리 현황")
print(f"  완료:   {n_ok}개")
print(f"  처리중: {n_run}개")
print(f"  실패:   {n_fail}개")
print(f"  전체:   {n_ok + n_run + n_fail}개")

if n_run == 0 and n_ok > 0:
    print("\n→ 모두 완료됐습니다. 02_download.py 를 실행하세요.")
else:
    print(f"\n→ 아직 처리 중입니다. 잠시 후 다시 확인하세요.")
