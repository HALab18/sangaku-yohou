# -*- coding: utf-8 -*-
"""山岳地点予報取得スクリプト (Open-Meteo API)

使い方:
  python mountain_weather.py --name 燕岳
  python mountain_weather.py --name 燕岳 --select 2
  python mountain_weather.py --name 天狗岳 --date 2026-07-19 --days 2
  python mountain_weather.py --lat 36.407 --lon 137.713 --elev 2763 --label 燕岳
  python mountain_weather.py --name 燕岳 --weekly
  python mountain_weather.py --name 燕岳 --date 2026-07-19 --compare-models

終了コード: 0=正常 / 2=山名の候補が複数(要選択) / 1=エラー
"""
import argparse
import contextlib
import csv
import datetime as dt
import html as html_mod
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
MOUNTAINS_CSV = Path(__file__).resolve().parent.parent / "references" / "mountains.csv"

# 気圧面と標準高度 (m)。山頂標高を挟む2面から線形補間して稜線風を出す
PRESSURE_LEVELS = [(925, 760), (900, 990), (850, 1460), (800, 1950), (700, 3010), (600, 4200)]

WMO_CODES = {
    0: "快晴", 1: "晴れ", 2: "晴れ時々曇り", 3: "曇り",
    45: "霧", 48: "着氷性の霧",
    51: "霧雨(弱)", 53: "霧雨", 55: "霧雨(強)",
    56: "着氷性霧雨", 57: "着氷性霧雨(強)",
    61: "雨(弱)", 63: "雨", 65: "雨(強)",
    66: "着氷性の雨", 67: "着氷性の雨(強)",
    71: "雪(弱)", 73: "雪", 75: "雪(強)", 77: "霧雪",
    80: "にわか雨(弱)", 81: "にわか雨", 82: "にわか雨(強)",
    85: "にわか雪", 86: "にわか雪(強)",
    95: "雷雨", 96: "雷雨(雹)", 99: "雷雨(激しい雹)",
}

DIR16 = ["北", "北北東", "北東", "東北東", "東", "東南東", "南東", "南南東",
         "南", "南南西", "南西", "西南西", "西", "西北西", "北西", "北北西"]


def wdir(deg):
    if deg is None:
        return "-"
    return DIR16[int((deg + 11.25) % 360 / 22.5)]


def wcode(code):
    if code is None:
        return "-"
    return WMO_CODES.get(int(code), f"code{int(code)}")


def http_json(url, params, retries=3):
    """一時的な通信エラー(接続断・SSLハンドシェイクタイムアウト・5xx等)は指数バックオフで再試行する"""
    q = urllib.parse.urlencode(params, safe=",")
    req = urllib.request.Request(f"{url}?{q}", headers={"User-Agent": "sangaku-yohou-skill"})
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code < 500 or attempt == retries:
                sys.exit(f"ERROR: API呼び出しに失敗しました ({url}): HTTP {e.code} {e.reason}")
        except Exception as e:
            last_err = e
            if attempt == retries:
                break
        wait = 1.5 * attempt
        print(f"通信エラーのため再試行します ({attempt}/{retries}, {wait:.0f}秒後): {last_err}",
              file=sys.stderr)
        time.sleep(wait)
    sys.exit(f"ERROR: API呼び出しに{retries}回失敗しました ({url}): {last_err}\n"
             f"ネットワーク接続、プロキシ設定、セキュリティソフトのSSL検査機能を確認してください。")


# ---------------------------------------------------------------- 山名解決
def load_csv():
    rows = []
    if MOUNTAINS_CSV.exists():
        with open(MOUNTAINS_CSV, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    return rows


def resolve_mountain(name, select=None):
    """(label, lat, lon, elev, source) を返す。曖昧なら候補を表示して exit(2)"""
    rows = load_csv()
    hits = [r for r in rows if r["name"] == name or r.get("yomi") == name]
    if not hits:
        hits = [r for r in rows if name in r["name"]]
    if len(hits) == 1:
        r = hits[0]
        return (f'{r["name"]}({r["pref"]})', float(r["lat"]), float(r["lon"]),
                float(r["elev"]), "内蔵DB")
    if len(hits) > 1:
        if select and 1 <= select <= len(hits):
            r = hits[select - 1]
            return (f'{r["name"]}({r["pref"]})', float(r["lat"]), float(r["lon"]),
                    float(r["elev"]), "内蔵DB")
        print(f"「{name}」は複数候補があります。--select N で選択してください:")
        for i, r in enumerate(hits, 1):
            print(f"  {i}. {r['name']}({r['pref']}) {r['elev']}m")
        sys.exit(2)

    # ジオコーディングAPI
    data = http_json(GEOCODE_URL, {"name": name, "count": 10, "language": "ja"})
    results = data.get("results") or []
    jp = [r for r in results if r.get("country_code") == "JP"]
    mt = [r for r in jp if r.get("feature_code") in ("MT", "PK", "VLC", "HLL", "MTS")]
    cands = mt or jp or results
    if not cands:
        sys.exit(f"ERROR: 「{name}」が見つかりませんでした。--lat/--lon/--elev で直接指定してください。")
    if len(cands) > 1 and not select:
        print(f"「{name}」は複数候補があります(ジオコーディング)。--select N で選択してください:")
        for i, r in enumerate(cands, 1):
            print(f"  {i}. {r['name']}({r.get('admin1', '?')}{'/' + r['admin2'] if r.get('admin2') else ''}) "
                  f"標高{r.get('elevation', '?')}m [{r['latitude']:.4f}, {r['longitude']:.4f}]")
        sys.exit(2)
    r = cands[(select or 1) - 1]
    elev = r.get("elevation")
    if elev is None:
        sys.exit(f"ERROR: 標高情報が取得できません。--elev で指定してください。")
    return (f'{r["name"]}({r.get("admin1", "?")})', r["latitude"], r["longitude"],
            float(elev), "ジオコーディング(標高はグリッド値: 実際の山頂標高と差がある場合あり)")


# ---------------------------------------------------------------- 稜線風
def bracket_levels(elev):
    """山頂標高を挟む気圧面のペア(下,上)と補間係数を返す"""
    lv = PRESSURE_LEVELS
    if elev <= lv[0][1]:
        return lv[0], lv[0], 0.0
    for i in range(len(lv) - 1):
        lo, hi = lv[i], lv[i + 1]
        if lo[1] <= elev <= hi[1]:
            t = (elev - lo[1]) / (hi[1] - lo[1])
            return lo, hi, t
    return lv[-1], lv[-1], 0.0


def ridge_wind(h, i, lo, hi, t):
    """i時刻の稜線風速(m/s)・風向を気圧面2面から補間"""
    s_lo = h.get(f"wind_speed_{lo[0]}hPa", [None])[i]
    s_hi = h.get(f"wind_speed_{hi[0]}hPa", [None])[i]
    d_lo = h.get(f"wind_direction_{lo[0]}hPa", [None])[i]
    d_hi = h.get(f"wind_direction_{hi[0]}hPa", [None])[i]
    if s_lo is None or s_hi is None:
        s = s_lo if s_lo is not None else s_hi
        d = d_lo if d_lo is not None else d_hi
        return s, d
    speed = s_lo + (s_hi - s_lo) * t
    d = d_lo if t < 0.5 else d_hi
    return speed, d


# ---------------------------------------------------------------- 登山指数
def block_index(ridge_ws, precip_3h, prob, cape):
    """3時間ブロックの登山指数 A/B/C (最悪値採用)"""
    idx = "A"

    def worse(v):
        nonlocal idx
        if v == "C" or idx == "C":
            idx = "C"
        elif v == "B":
            idx = "B"

    if ridge_ws is not None:
        if ridge_ws >= 15:
            worse("C")
        elif ridge_ws >= 10:
            worse("B")
    if precip_3h is not None:
        if precip_3h >= 5:
            worse("C")
        elif precip_3h >= 1:
            worse("B")
    if prob is not None and prob >= 70:
        worse("B")
    if cape is not None:
        if cape >= 1000:
            worse("C")
        elif cape >= 500:
            worse("B")
    return idx


IDX_MARK = {"A": "A◎", "B": "B△", "C": "C✕"}


# ---------------------------------------------------------------- 眺望
def view_score(elev, low, mid, high, precip_3h, vis):
    """山頂からの眺望 ◎/○/△/✕。雲層(下層<2km/中層2-7km/上層>7km)を山頂標高と比較。
    山頂レベルの雲=ガス、山頂より下の雲=雲海の可能性。"""
    if elev < 2000:
        summit_cl = max(v for v in (low, mid) if v is not None) if (low is not None or mid is not None) else None
        below_cl = None  # 低山は下に雲層バンドなし(谷霧は表現できない)
    else:
        summit_cl = mid
        below_cl = low
    if precip_3h is not None and precip_3h >= 1:
        return "✕", "雨"
    if vis is not None and vis < 2000:
        return "✕", "ガス"
    if summit_cl is not None and summit_cl >= 80:
        return "✕", "ガス"
    if (summit_cl is not None and summit_cl >= 50) or (vis is not None and vis < 10000):
        return "△", ""
    unkai = below_cl is not None and below_cl >= 60 and (summit_cl or 0) <= 30
    if (summit_cl or 0) <= 20 and (vis is None or vis >= 20000):
        return "◎", "雲海" if unkai else ""
    return "○", "雲海" if unkai else ""


# ---------------------------------------------------------------- 予報取得
def fetch_forecast(lat, lon, elev, start, end, levels):
    hourly = ["temperature_2m", "precipitation", "precipitation_probability",
              "weather_code", "cloud_cover_low", "cloud_cover_mid", "cloud_cover_high",
              "wind_speed_10m", "wind_gusts_10m",
              "freezing_level_height", "cape", "visibility"]
    for p, _ in levels:
        hourly += [f"wind_speed_{p}hPa", f"wind_direction_{p}hPa"]
    params = {
        "latitude": lat, "longitude": lon, "elevation": elev,
        "hourly": ",".join(dict.fromkeys(hourly)),
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                 "precipitation_sum,precipitation_probability_max,sunrise,sunset",
        "timezone": "Asia/Tokyo", "wind_speed_unit": "ms",
        "start_date": start.isoformat(), "end_date": end.isoformat(),
    }
    return http_json(FORECAST_URL, params)


def day_indices(times, date):
    pre = date.isoformat()
    return [i for i, t in enumerate(times) if t.startswith(pre)]


def fnum(v, fmt="{:.0f}", none="-"):
    return none if v is None else fmt.format(v)


# ---------------------------------------------------------------- 出力
def print_detail_day(data, date, lo, hi, t, elev):
    h = data["hourly"]
    times = h["time"]
    idxs = day_indices(times, date)
    if not idxs:
        return
    d = data["daily"]
    suntxt = ""
    try:
        di = d["time"].index(date.isoformat())
        if d.get("sunrise") and d["sunrise"][di]:
            suntxt = f" (日の出{d['sunrise'][di][11:16]} / 日の入{d['sunset'][di][11:16]})"
    except (ValueError, KeyError):
        pass
    print(f"\n### {date.isoformat()} ({'月火水木金土日'[date.weekday()]}) 3時間ごと詳細{suntxt}")
    print("| 時刻 | 天気 | 眺望 | 気温 | 体感 | 稜線風 | 突風 | 降水 | 降水% | 雷CAPE | 雲(下/中/上) | 視程 | 凍結高度 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for start_h in range(0, 24, 3):
        block = [i for i in idxs if int(times[i][11:13]) // 3 * 3 == start_h]
        if not block:
            continue
        i0 = block[0]
        temp = h["temperature_2m"][i0]
        rws = [ridge_wind(h, i, lo, hi, t) for i in block]
        ws = max((s for s, _ in rws if s is not None), default=None)
        wd = next((d for s, d in rws if s == ws), None)
        gust = max((h["wind_gusts_10m"][i] for i in block if h["wind_gusts_10m"][i] is not None), default=None)
        pr = sum(h["precipitation"][i] or 0 for i in block)
        prob = max((h["precipitation_probability"][i] for i in block
                    if h["precipitation_probability"][i] is not None), default=None)
        cape = max((h["cape"][i] for i in block if h["cape"][i] is not None), default=None)
        fl = h["freezing_level_height"][i0]
        feel = None if (temp is None or ws is None) else temp - ws  # 慣用則: 風速1m/sで-1℃
        cl = f'{fnum(h["cloud_cover_low"][i0])}/{fnum(h["cloud_cover_mid"][i0])}/{fnum(h["cloud_cover_high"][i0])}%'
        vis_all = h.get("visibility") or []
        vis = min((vis_all[i] for i in block if i < len(vis_all) and vis_all[i] is not None), default=None)
        vw, note = view_score(elev, h["cloud_cover_low"][i0], h["cloud_cover_mid"][i0],
                              h["cloud_cover_high"][i0], pr, vis)
        vw_txt = vw + (f"({note})" if note else "")
        vis_txt = "-" if vis is None else (f"{vis / 1000:.0f}km" if vis >= 1000 else f"{vis:.0f}m")
        print(f"| {start_h:02d}時 | {wcode(h['weather_code'][i0])} | {vw_txt} | {fnum(temp, '{:.1f}')}℃ "
              f"| {fnum(feel, '{:.0f}')}℃ | {wdir(wd)} {fnum(ws, '{:.1f}')}m/s | {fnum(gust, '{:.0f}')}m/s "
              f"| {pr:.1f}mm | {fnum(prob)}% | {fnum(cape)} | {cl} | {vis_txt} | {fnum(fl)}m |")


def morning_view(h, times, idxs, elev):
    """朝(4-8時)の眺望の最良値。ご来光・朝の展望の目安"""
    order = {"◎": 0, "○": 1, "△": 2, "✕": 3}
    best, best_note = None, ""
    vis_all = h.get("visibility") or []
    for i in idxs:
        hr = int(times[i][11:13])
        if not 4 <= hr <= 8:
            continue
        vis = vis_all[i] if i < len(vis_all) else None
        pr3 = (h["precipitation"][i] or 0) * 3
        vw, note = view_score(elev, h["cloud_cover_low"][i], h["cloud_cover_mid"][i],
                              h["cloud_cover_high"][i], pr3, vis)
        if best is None or order[vw] < order[best]:
            best, best_note = vw, note
    if best is None:
        return "-"
    return best + (f"({best_note})" if best_note else "")


def daily_summary_rows(data, dates, lo, hi, t, elev):
    h = data["hourly"]
    d = data["daily"]
    times = h["time"]
    rows = []
    for date in dates:
        try:
            di = d["time"].index(date.isoformat())
        except ValueError:
            continue
        idxs = day_indices(times, date)
        # 行動時間帯 5-16時で指数判定
        act = [i for i in idxs if 5 <= int(times[i][11:13]) <= 16]
        day_idx = "A"
        ws_max, wd_max = None, None
        for start_h in range(3, 18, 3):
            block = [i for i in act if int(times[i][11:13]) // 3 * 3 == start_h]
            if not block:
                continue
            rws = [ridge_wind(h, i, lo, hi, t) for i in block]
            ws = max((s for s, _ in rws if s is not None), default=None)
            if ws is not None and (ws_max is None or ws > ws_max):
                ws_max = ws
                wd_max = next((dd for s, dd in rws if s == ws), None)
            pr = sum(h["precipitation"][i] or 0 for i in block)
            prob = max((h["precipitation_probability"][i] for i in block
                        if h["precipitation_probability"][i] is not None), default=None)
            cape = max((h["cape"][i] for i in block if h["cape"][i] is not None), default=None)
            bi = block_index(ws, pr, prob, cape)
            if bi == "C" or (bi == "B" and day_idx == "A"):
                day_idx = bi
        fls = [h["freezing_level_height"][i] for i in idxs if h["freezing_level_height"][i] is not None]
        rows.append({
            "date": date, "idx": day_idx, "code": d["weather_code"][di],
            "tmin": d["temperature_2m_min"][di], "tmax": d["temperature_2m_max"][di],
            "ws": ws_max, "wd": wd_max,
            "pr": d["precipitation_sum"][di], "prob": d["precipitation_probability_max"][di],
            "fl": min(fls) if fls else None,
            "view": morning_view(h, times, idxs, elev),
        })
    return rows


def print_daily_summary(rows, title):
    print(f"\n### {title}")
    print("| 日付 | 指数 | 天気 | 眺望(朝) | 山頂気温 | 稜線風max(5-16時) | 降水量 | 降水% | 凍結高度min |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        wj = "月火水木金土日"[r["date"].weekday()]
        print(f"| {r['date'].strftime('%m/%d')}({wj}) | {IDX_MARK[r['idx']]} | {wcode(r['code'])} "
              f"| {r['view']} | {fnum(r['tmin'], '{:.0f}')}〜{fnum(r['tmax'], '{:.0f}')}℃ "
              f"| {wdir(r['wd'])} {fnum(r['ws'], '{:.1f}')}m/s "
              f"| {fnum(r['pr'], '{:.1f}')}mm | {fnum(r['prob'])}% | {fnum(r['fl'])}m |")


def compare_models(lat, lon, elev, start, end):
    models = ["jma_seamless", "ecmwf_ifs025", "gfs_seamless"]
    labels = {"jma_seamless": "気象庁JMA", "ecmwf_ifs025": "欧州ECMWF", "gfs_seamless": "米国GFS"}
    params = {
        "latitude": lat, "longitude": lon, "elevation": elev,
        "hourly": "temperature_2m,precipitation,wind_speed_10m,cloud_cover",
        "timezone": "Asia/Tokyo", "wind_speed_unit": "ms",
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "models": ",".join(models),
    }
    data = http_json(FORECAST_URL, params)
    h = data["hourly"]
    times = h["time"]
    print(f"\n### モデル間比較（予報の確度確認: 各モデルが一致するほど信頼度が高い）")
    print("| 日付 | モデル | 気温min〜max | 降水量 | 10m風max | 平均雲量 |")
    print("|---|---|---|---|---|---|")
    date = start
    while date <= end:
        idxs = day_indices(times, date)
        for m in models:
            def col(v):
                key = f"{v}_{m}"
                if key not in h:
                    key = v
                return [h[key][i] for i in idxs if h.get(key) and h[key][i] is not None]
            temps, precs = col("temperature_2m"), col("precipitation")
            winds, clouds = col("wind_speed_10m"), col("cloud_cover")
            if not temps:
                print(f"| {date.strftime('%m/%d')} | {labels[m]} | (データなし) | | | |")
                continue
            print(f"| {date.strftime('%m/%d')} | {labels[m]} | {min(temps):.0f}〜{max(temps):.0f}℃ "
                  f"| {sum(precs):.1f}mm | {max(winds):.1f}m/s | {sum(clouds) / len(clouds):.0f}% |")
        date += dt.timedelta(days=1)


# ---------------------------------------------------------------- HTML出力
HTML_CSS = """
:root{--accent:#2d6a4f;--accent2:#b5451b;--night:#1e2d4a;--warn:#7b5e00;--bg:#f7f5f0}
*{box-sizing:border-box}
body{margin:0;padding:16px;background:var(--bg);color:#222;
  font-family:"Hiragino Kaku Gothic ProN","Yu Gothic UI","Meiryo",system-ui,sans-serif;
  font-size:14px;line-height:1.6}
main{max-width:1080px;margin:0 auto}
h1{color:var(--accent);font-size:1.4em;border-bottom:3px solid var(--accent);
  padding-bottom:6px;margin:0 0 12px}
h2{color:var(--night);font-size:1.1em;margin:22px 0 8px;border-left:5px solid var(--accent);
  padding-left:8px}
ul.meta{margin:0 0 8px;padding-left:1.2em;color:#555;font-size:.92em}
.tbl{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:6px 0 4px}
table{border-collapse:collapse;white-space:nowrap;width:100%}
th{background:var(--accent);color:#fff;padding:6px 9px;font-weight:600;font-size:.92em}
td{padding:5px 9px;border-bottom:1px solid #e2ddd2;text-align:center;background:#fff}
tr:nth-child(even) td{background:#f3f0e8}
.b{display:inline-block;min-width:2.6em;padding:1px 7px;border-radius:10px;
  font-weight:700;font-size:.92em}
.b-a{background:#d8efe1;color:#1c5b3f}.b-b{background:#fdeec9;color:#7b5e00}
.b-c{background:#f9d9cf;color:#a03415}
.v-ex{color:#1c5b3f;font-weight:700}.v-ok{color:#2d6a4f}.v-so{color:#7b5e00}
.v-ng{color:#a03415}
.sat{color:#1857a4;font-weight:600}.sun{color:#c0392b;font-weight:600}
.notice{background:#fff8e6;border-left:5px solid var(--warn);padding:10px 12px;
  border-radius:0 6px 6px 0;margin:18px 0;font-size:.92em}
footer{color:#888;font-size:.85em;margin-top:20px}
@media(max-width:600px){body{padding:8px;font-size:13px}}
"""


def _decorate_cell(cell):
    """表セル内の指数/眺望/曜日マークに色クラスを付与"""
    c = html_mod.escape(cell)
    for mark, cls in (("A◎", "b b-a"), ("B△", "b b-b"), ("C✕", "b b-c")):
        if c == mark:
            return f'<span class="{cls}">{mark}</span>'
    m = re.match(r"^([◎○△✕])(\(.+\))?$", c)
    if m:
        cls = {"◎": "v-ex", "○": "v-ok", "△": "v-so", "✕": "v-ng"}[m.group(1)]
        return f'<span class="{cls}">{c}</span>'
    c = c.replace("(土)", '<span class="sat">(土)</span>').replace("(日)", '<span class="sun">(日)</span>')
    return c


def md_to_html(md, title):
    """本スクリプトが出力するMarkdown(見出し/箇条書き/表/引用)をHTMLに変換"""
    out, table, ul = [], [], False

    def flush_table():
        nonlocal table
        if not table:
            return
        out.append('<div class="tbl"><table>')
        for ri, row in enumerate(table):
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            if ri == 1 and all(set(c) <= set("-: ") for c in cells):
                continue
            tag = "th" if ri == 0 else "td"
            out.append("<tr>" + "".join(
                f"<{tag}>{_decorate_cell(c) if tag == 'td' else html_mod.escape(c)}</{tag}>"
                for c in cells) + "</tr>")
        out.append("</table></div>")
        table = []

    def flush_ul():
        nonlocal ul
        if ul:
            out.append("</ul>")
            ul = False

    for line in md.splitlines():
        if line.startswith("|"):
            flush_ul()
            table.append(line)
            continue
        flush_table()
        if line.startswith("## "):
            flush_ul()
            out.append(f"<h1>{html_mod.escape(line[3:])}</h1>")
        elif line.startswith("### "):
            flush_ul()
            out.append(f"<h2>{html_mod.escape(line[4:])}</h2>")
        elif line.startswith("- "):
            if not ul:
                out.append('<ul class="meta">')
                ul = True
            out.append(f"<li>{html_mod.escape(line[2:])}</li>")
        elif line.startswith("> "):
            flush_ul()
            out.append(f'<div class="notice">{html_mod.escape(line[2:])}</div>')
        elif line.strip():
            flush_ul()
            out.append(f"<p>{html_mod.escape(line)}</p>")
    flush_table()
    flush_ul()
    out.append("<footer>データ: Open-Meteo (CC BY 4.0) / sangaku-yohou</footer>")
    return ("<!doctype html><html lang='ja'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html_mod.escape(title)}</title><style>{HTML_CSS}</style></head>"
            "<body><main>" + "\n".join(out) + "</main></body></html>")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", help="山名")
    ap.add_argument("--select", type=int, help="候補が複数の時に選ぶ番号")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--elev", type=float, help="山頂標高m (この高さの気象を出す)")
    ap.add_argument("--label", default="指定地点")
    ap.add_argument("--date", help="対象日 YYYY-MM-DD (省略時は今日から)")
    ap.add_argument("--days", type=int, default=3, help="詳細表示する日数 (既定3)")
    ap.add_argument("--weekly", action="store_true", help="16日間の日別見通しを表示")
    ap.add_argument("--compare-models", action="store_true", help="JMA/ECMWF/GFSモデル比較")
    ap.add_argument("--html", nargs="?", const="AUTO", metavar="PATH",
                    help="HTMLレポートも保存 (パス省略時はカレントに自動命名)")
    ap.add_argument("--open", action="store_true", help="--html 保存後にブラウザで開く")
    args = ap.parse_args()

    if args.name:
        label, lat, lon, elev, src = resolve_mountain(args.name, args.select)
        if args.elev:
            elev, src = args.elev, src + " (標高は指定値)"
    elif args.lat is not None and args.lon is not None and args.elev is not None:
        label, lat, lon, elev, src = args.label, args.lat, args.lon, args.elev, "座標指定"
    else:
        ap.error("--name か --lat/--lon/--elev を指定してください")

    today = dt.date.today()
    horizon = today + dt.timedelta(days=15)
    if args.date:
        start = dt.date.fromisoformat(args.date)
        if start > horizon:
            sys.exit(f"ERROR: {args.date} は予報範囲外です(最長16日先={horizon}まで)。"
                     f"直前に再確認してください。")
        if start < today:
            sys.exit(f"ERROR: {args.date} は過去日です。予報は本日以降のみ対応です。")
    else:
        start = today
    detail_end = min(start + dt.timedelta(days=max(args.days, 1) - 1), horizon)
    fetch_start = today  # 週間サマリは常に今日から
    fetch_end = horizon if args.weekly else min(max(today + dt.timedelta(days=6), detail_end), horizon)

    lo, hi, t = bracket_levels(elev)
    data = fetch_forecast(lat, lon, elev, fetch_start, fetch_end, {lo, hi})

    def emit():
        lv = f"{lo[0]}hPa" if lo == hi else f"{lo[0]}/{hi[0]}hPa補間"
        print(f"## {label} の山岳気象予報")
        print(f"- 地点: 北緯{lat:.4f} 東経{lon:.4f} / 標高 {elev:.0f}m ({src})")
        print(f"- 稜線風: {lv} の風を山頂標高に合わせて算出 / 気温は標高{elev:.0f}m面の値")
        print(f"- 体感温度 = 気温 − 稜線風速×1 (慣用則) / 取得: {dt.datetime.now():%Y-%m-%d %H:%M} / 出典: Open-Meteo")

        n_days = (fetch_end - fetch_start).days + 1
        dates = [fetch_start + dt.timedelta(days=i) for i in range(n_days)]
        rows = daily_summary_rows(data, dates, lo, hi, t, elev)
        title = "16日間の見通し" if args.weekly else "日別サマリ"
        print_daily_summary(rows, title)

        d = start
        while d <= detail_end:
            print_detail_day(data, d, lo, hi, t, elev)
            d += dt.timedelta(days=1)

        if args.compare_models:
            compare_models(lat, lon, elev, start, min(detail_end, start + dt.timedelta(days=2)))

        print("\n> ⚠️ 数値予報は山岳地形では誤差が大きく、局地的な突風・雷雨・視界不良は表現しきれません。"
              "登山指数は目安です。最終判断は最新の予報と現地の状況で行ってください。")

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        emit()
    md = buf.getvalue()
    sys.stdout.write(md)

    if args.html:
        page_title = f"{label} 山岳気象予報 {start.strftime('%m/%d')}"
        if args.html == "AUTO":
            safe = re.sub(r"[^\w぀-ヿ一-鿿]+", "_", label).strip("_")
            path = Path.cwd() / f"yohou_{safe}_{start.isoformat()}.html"
        else:
            path = Path(args.html)
        path.write_text(md_to_html(md, page_title), encoding="utf-8")
        print(f"\nHTML保存: {path}")
        if args.open:
            import webbrowser
            webbrowser.open(path.as_uri())


if __name__ == "__main__":
    main()
