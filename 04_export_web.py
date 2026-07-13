# -*- coding: utf-8 -*-
"""
[4단계] MintPy 산출물 → 웹페이지용 경량 데이터(data_{코드}.js) 추출
실행:  python 04_export_web.py [공항번호]
"""
import json
import sys
from datetime import date
from pathlib import Path

import h5py
import numpy as np
from pyproj import Transformer

from airports import select_airport, AIRPORT_BUF, AIRPORTS


def get_airport():
    """CLI 인수(공항 번호)가 있으면 바로 선택, 없으면 대화형 메뉴."""
    if len(sys.argv) > 1:
        try:
            sel = int(sys.argv[1])
            if 1 <= sel <= len(AIRPORTS):
                return AIRPORTS[sel - 1]
        except ValueError:
            pass
    return select_airport()


airport = get_airport()
print(f"\n[선택] {airport['name']} ({airport['code']})")

code = airport["code"]
try:
    RES = int(sys.argv[2]) if len(sys.argv) > 2 else 80
except ValueError:
    RES = 80
D_SUFFIX   = f"_INT{RES}" if RES != 80 else ""
MINTPY_DIR = Path("mintpy") / (code + D_SUFFIX)
OUT        = Path(f"data_{code}.js")
region_airports = [
    {"code": code, "name": airport["name"],
     "lat": airport["lat"], "lon": airport["lon"]}
]

if not MINTPY_DIR.exists():
    raise SystemExit(f"{MINTPY_DIR} 가 없습니다. 03번 스크립트를 먼저 실행하세요.")


def pick(*names):
    for n in names:
        p = MINTPY_DIR / n
        if p.exists():
            return p
    raise FileNotFoundError(f"{names} 를 찾을 수 없습니다.")


vel_f = pick("velocity.h5")
ts_f  = pick("timeseries_demErr.h5", "timeseries.h5")
msk_f = pick("maskTempCoh.h5")

with h5py.File(vel_f) as f:
    vel = f["velocity"][:] * 1000.0
    at  = dict(f.attrs)

def A(key):
    v = at[key]
    return v.decode() if isinstance(v, bytes) else v

x0, dx = float(A("X_FIRST")), float(A("X_STEP"))
y0, dy = float(A("Y_FIRST")), float(A("Y_STEP"))
epsg   = A("EPSG") if "EPSG" in at else None

with h5py.File(msk_f) as f:
    mask = f["mask"][:].astype(bool)
with h5py.File(ts_f) as f:
    raw_dates = [d.decode()[:8] for d in f["date"][:]]
    dates = raw_dates
    ts    = f["timeseries"][:] * 1000.0

rows, cols = vel.shape
jj, ii = np.meshgrid(np.arange(cols), np.arange(rows))
xs = x0 + (jj + 0.5) * dx
ys = y0 + (ii + 0.5) * dy
if epsg and str(epsg) != "4326":
    tr = Transformer.from_crs(f"EPSG:{int(float(epsg))}", "EPSG:4326", always_xy=True)
    lon_arr, lat_arr = tr.transform(xs, ys)
else:
    lon_arr, lat_arr = xs, ys

valid = mask & np.isfinite(vel)
cells = []
for i, j in zip(*np.where(valid)):
    series = ts[:, i, j]
    series = series - series[0]
    cells.append({
        "lat": round(float(lat_arr[i, j]), 5),
        "lon": round(float(lon_arr[i, j]), 5),
        "v":   round(float(vel[i, j]), 1),
        "ts":  [round(float(s), 1) for s in series],
    })

data = {
    "code":        code,
    "generated":   date.today().isoformat(),
    "dates":       [f"{d[:4]}.{d[4:6]}.{d[6:8]}" for d in dates],
    "cell_m":      abs(dx),
    "airport_buf": AIRPORT_BUF,
    "airports":    region_airports,
    "cells":       cells,
}

OUT.write_text(
    "window.KAC_DATA = window.KAC_DATA || {};\n"
    "window.KAC_DATA['" + data["code"] + "'] = "
    + json.dumps(data, ensure_ascii=False) + ";\n",
    encoding="utf-8"
)
mb = OUT.stat().st_size / 1e6
print(f"완료: {OUT.name} ({mb:.1f} MB, 유효 격자 {len(cells)}개, 관측 {len(dates)}회)")
