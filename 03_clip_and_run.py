# -*- coding: utf-8 -*-
"""
[3단계] 간섭도들을 공항 일대 공통 격자로 절단 → MintPy(SBAS) 시계열 분석
실행:  python 03_clip_and_run.py
산출:  ./mintpy/{공항코드}/velocity.h5 (침하속도), timeseries*.h5 (누적변위)
소요:  PC 사양에 따라 수십 분 수준
"""
import shutil
import subprocess
import sys
from pathlib import Path

from osgeo import gdal, osr

from airports import select_airport, BUF, AIRPORT_BUF

gdal.UseExceptions()

airport = select_airport()
print(f"\n[선택] {airport['name']} ({airport['code']})")

lon, lat = airport["lon"], airport["lat"]
W, E = lon - BUF, lon + BUF
S, N = lat - BUF, lat + BUF

RES      = 500
CLIP     = Path("clipped")       / airport["code"]
MINTPY_DIR = Path("mintpy")      / airport["code"]

# 해당 공항 데이터 없으면 다른 공항 데이터 재활용 (같은 Sentinel-1 패스 커버리지)
SRC = Path("hyp3_products") / airport["code"]
if not SRC.exists() or not any(SRC.iterdir()):
    candidates = sorted(
        d for d in Path("hyp3_products").iterdir()
        if d.is_dir() and any(d.iterdir())
    )
    if not candidates:
        sys.exit("hyp3_products 폴더에 데이터가 없습니다. 02번 스크립트를 먼저 실행하세요.")
    SRC = candidates[0]
    print(f"[정보] {airport['code']} 전용 데이터 없음 → {SRC.name} 데이터 재활용")


def utm_bounds(sample_tif):
    ds  = gdal.Open(str(sample_tif))
    dst = osr.SpatialReference(ds.GetProjection())
    src = osr.SpatialReference(); src.ImportFromEPSG(4326)
    src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    dst.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    tr  = osr.CoordinateTransformation(src, dst)
    xs, ys = zip(*[tr.TransformPoint(x, y)[:2]
                   for x, y in [(W, S), (W, N), (E, S), (E, N)]])
    return (min(xs) // RES * RES, min(ys) // RES * RES,
            -(-max(xs) // RES) * RES, -(-max(ys) // RES) * RES,
            ds.GetProjection())


SUFFIXES = ["_unw_phase.tif", "_corr.tif", "_dem.tif",
            "_lv_theta.tif", "_lv_phi.tif"]

prods = sorted(d for d in SRC.iterdir() if d.is_dir())
if not prods:
    sys.exit("해당 공항의 hyp3_products 폴더가 비어 있습니다. 02번 스크립트를 먼저 실행하세요.")
print(f"[절단] 간섭도 {len(prods)}개 → 공통 격자(약 {RES}m)로 자르는 중")

sample = next(prods[0].glob("*_unw_phase.tif"))
xmin, ymin, xmax, ymax, proj = utm_bounds(sample)

CLIP.mkdir(parents=True, exist_ok=True)
for d in prods:
    out_dir = CLIP / d.name
    out_dir.mkdir(exist_ok=True)
    for suf in SUFFIXES:
        tifs = list(d.glob(f"*{suf}"))
        if not tifs:
            print(f"  ! {d.name} 에 {suf} 없음 — 건너뜀")
            continue
        out = out_dir / tifs[0].name
        if out.exists():
            continue
        gdal.Warp(str(out), str(tifs[0]), dstSRS=proj,
                  outputBounds=(xmin, ymin, xmax, ymax),
                  xRes=RES, yRes=RES, targetAlignedPixels=False,
                  resampleAlg="near")
    for txt in d.glob("*.txt"):
        shutil.copy(txt, out_dir / txt.name)
print("[절단] 완료")

MINTPY_DIR.mkdir(parents=True, exist_ok=True)
cfg = MINTPY_DIR / "smallbaselineApp.cfg"
code = airport['code']
cfg.write_text(f"""\
mintpy.compute.cluster        = local
mintpy.load.processor         = hyp3
mintpy.load.unwFile           = ../../clipped/{code}/*/*_unw_phase.tif
mintpy.load.corFile           = ../../clipped/{code}/*/*_corr.tif
mintpy.load.demFile           = ../../clipped/{code}/*/*_dem.tif
mintpy.load.incAngleFile      = ../../clipped/{code}/*/*_lv_theta.tif
mintpy.load.azAngleFile       = ../../clipped/{code}/*/*_lv_phi.tif
mintpy.network.coherenceBased = yes
mintpy.troposphericDelay.method = no
mintpy.topographicResidual    = yes
mintpy.deramp                 = linear
""", encoding="utf-8")
print(f"[MintPy] 설정 생성: {cfg}")

print("[MintPy] 시계열 분석 시작 (수십 분 소요될 수 있음)")
mintpy_exe = Path(sys.executable).parent / "Scripts" / "smallbaselineApp.py.exe"
r = subprocess.run([str(mintpy_exe), "smallbaselineApp.cfg"], cwd=MINTPY_DIR)
if r.returncode != 0:
    sys.exit("MintPy 실행 중 오류가 발생했습니다. 출력 메시지를 복사해서 알려주세요.")
print(f"\n완료. 다음으로 04_export_web.py 를 실행하세요. (공항: {airport['name']})")
