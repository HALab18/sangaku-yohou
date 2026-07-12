# sangaku-yohou — 山岳地点予報ツール

特定の山の山頂・稜線の数値予報（稜線風・気温・体感温度・凍結高度・降水・雷CAPE・
眺望指数・登山指数・週間見通し）を Open-Meteo API から取得して Markdown 表で出力する。

依存: Python 3 標準ライブラリのみ / APIキー不要（Open-Meteo・国土地理院API）

## 使い方

```
python scripts\mountain_weather.py --name 燕岳
python scripts\mountain_weather.py --name 燕岳 --date 2026-07-19 --days 2
python scripts\mountain_weather.py --name 燕岳 --weekly            # 16日間の見通し
python scripts\mountain_weather.py --name 燕岳 --compare-models    # JMA/ECMWF/GFS比較
python scripts\mountain_weather.py --lat 36.407 --lon 137.713 --elev 2763 --label 任意地点
```

- 山名は `references/mountains.csv`（百名山＋人気峰147座、国土地理院DEMで座標照合済み）
  →国土地理院/Open-Meteoジオコーディングの順で解決。同名山は候補提示→`--select N`
- 終了コード: 0=正常 / 2=候補複数 / 1=エラー

## ファイル構成

```
scripts/mountain_weather.py   本体（scripts/ と references/ は同じ親直下に置くこと）
references/mountains.csv      内蔵山岳DB (name,yomi,pref,lat,lon,elev)
references/criteria.md        登山指数A/B/C・眺望指数◎○△✕の判定基準
```

## Claude Code スキル連携

`C:\Users\feto_\.claude\skills\sangaku-yohou\SKILL.md` がこのディレクトリの
スクリプトを参照している。本体をさらに移動する場合は SKILL.md のパスも更新すること。
