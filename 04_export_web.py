# -*- coding: utf-8 -*-
"""
[4단계] MintPy 산출물 → 웹페이지용 경량 데이터(data_{코드}.js) 추출
실행:  python 04_export_web.py
산출:  data_{공항코드}.js — 웹페이지 HTML과 같은 폴더에 두면 자동 반영
"""
import json
from datetime import date
from pathlib import Path

import h5py
import numpy as np
from pyproj import Transformer

from airports import select_airport, AIRPORT_BUF

airport = select_airport()
print(f"\n[선택] {airport['name']} ({airport['code']})")

MINTPY_DIR = Path("mintpy") / airport["code"]
OUT = Path(f"data_{airport['code']}.js")
COH_MIN = 0.7


def pick(*names):
    for n in names:
        p = MINTPY_DIR / n
        if p.exists():
            return p
    raise FileNotFoundError(f"{names} 를 찾을 수 없습니다. 03번 분석이 끝났는지 확인하세요.")


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
    dates = [d.decode()[:6] for d in f["date"][:]]
    ts    = f["timeseries"][:] * 1000.0

rows, cols = vel.shape
jj, ii = np.meshgrid(np.arange(cols), np.arange(rows))
xs = x0 + (jj + 0.5) * dx
ys = y0 + (ii + 0.5) * dy
if epsg and str(epsg) != "4326":
    tr = Transformer.from_crs(f"EPSG:{int(float(epsg))}", "EPSG:4326", always_xy=True)
    lon, lat = tr.transform(xs, ys)
else:
    lon, lat = xs, ys

valid = mask & np.isfinite(vel)
cells = []
for i, j in zip(*np.where(valid)):
    series = ts[:, i, j]
    series = series - series[0]
    cells.append({
        "lat": round(float(lat[i, j]), 5),
        "lon": round(float(lon[i, j]), 5),
        "v":   round(float(vel[i, j]), 1),
        "ts":  [round(float(s), 1) for s in series],
    })

data = {
    "airport":     airport["name"],
    "code":        airport["code"],
    "generated":   date.today().isoformat(),
    "dates":       [f"{d[:4]}.{d[4:6]}" for d in dates],
    "cell_m":      abs(dx),
    "center_lat":  airport["lat"],
    "center_lon":  airport["lon"],
    "airport_buf": AIRPORT_BUF,
    "cells":       cells,
}
OUT.write_text(
    "window.KAC_DATA = window.KAC_DATA || {};\n"
    "window.KAC_DATA['" + airport["code"] + "'] = "
    + json.dumps(data, ensure_ascii=False) + ";\n",
    encoding="utf-8"
)
mb = OUT.stat().st_size / 1e6
print(f"완료: {OUT.name} ({mb:.1f} MB, 유효 격자 {len(cells)}개, 관측 {len(dates)}회)")
