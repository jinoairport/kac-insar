# -*- coding: utf-8 -*-
"""
경상도권 5개 공항(PUS/TAE/HIN/USN/KPO)을 80m 해상도로 일괄 처리
실행:  python run_gyeongnam_80m.py
"""
import os
import subprocess
import sys
from pathlib import Path

# 스크립트 위치 기준으로 작업 디렉토리 고정
os.chdir(Path(__file__).parent)

# AIRPORTS 리스트에서의 1-indexed 번호
# 3=PUS, 4=TAE, 8=HIN, 9=USN, 10=KPO
CODES = [
    (3,  "PUS", "김해공항"),
    (4,  "TAE", "대구공항"),
    (8,  "HIN", "사천공항"),
    (9,  "USN", "울산공항"),
    (10, "KPO", "포항경주공항"),
]

for sel, code, name in CODES:
    mintpy_done = (Path("mintpy") / code / "velocity.h5").exists()
    data_done   = Path(f"data_{code}.js").exists()

    if mintpy_done and data_done:
        print(f"[건너뜀] {name} ({code}) — 이미 완료됨")
        continue

    if not mintpy_done:
        print(f"\n{'='*50}")
        print(f"[처리] {name} ({code}) — 03_clip_and_run.py 실행")
        print(f"{'='*50}")
        r = subprocess.run([sys.executable, "03_clip_and_run.py", str(sel)])
        if r.returncode != 0:
            print(f"[오류] {name} 처리 중 오류 발생. 중단합니다.")
            sys.exit(1)

    print(f"\n[내보내기] {name} ({code}) — 04_export_web.py 실행")
    r = subprocess.run([sys.executable, "04_export_web.py", str(sel)])
    if r.returncode != 0:
        print(f"[오류] {name} 내보내기 중 오류 발생. 중단합니다.")
        sys.exit(1)

print("\n" + "="*50)
print("경상도권 5개 공항 80m 처리 완료!")
print("생성된 파일: data_PUS.js, data_TAE.js, data_HIN.js, data_USN.js, data_KPO.js")
print("다음 단계: git add data_PUS.js data_TAE.js data_HIN.js data_USN.js data_KPO.js && git push")
print("="*50)
