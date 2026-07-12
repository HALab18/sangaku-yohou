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
python scripts\mountain_weather.py --name 燕岳 --html --open       # HTMLレポート保存+ブラウザ表示
python scripts\mountain_weather.py --name 燕岳 --html C:\tmp\yohou.html  # 保存先指定
```

`--html` は色分きのHTMLレポート（指数・眺望バッジ、スマホ対応、単一ファイル）を保存する。
パス省略時はカレントディレクトリに `yohou_<山名>_<日付>.html` で自動命名。
コンソールへのMarkdown出力は従来どおり並行して出る。

- 山名は `references/mountains.csv`（百名山＋人気峰147座、国土地理院DEMで座標照合済み）
  →国土地理院/Open-Meteoジオコーディングの順で解決。同名山は候補提示→`--select N`
- 終了コード: 0=正常 / 2=候補複数 / 1=エラー

## ファイル構成

```
scripts/mountain_weather.py   本体（scripts/ と references/ は同じ親直下に置くこと）
references/mountains.csv      内蔵山岳DB (name,yomi,pref,lat,lon,elev)
references/criteria.md        登山指数A/B/C・眺望指数◎○△✕の判定基準
skill/SKILL.md                Claude Code スキル定義のテンプレート
```

## 別PCでのセットアップ

1. このリポジトリをクローン
2. Python 3 が入っていることを確認（`python --version`。追加パッケージ不要）
3. 動作確認: `python scripts\mountain_weather.py --name 燕岳`
   - 社内プロキシ環境では `HTTPS_PROXY` の設定が必要な場合あり
   - SSL検査型セキュリティ製品下では証明書エラーが出ることがある

## Claude Code スキル連携（任意）

「〇〇岳の予報を調べて」でClaude Codeから自動起動させたい場合:

1. `skill/SKILL.md` を `~/.claude/skills/sangaku-yohou/SKILL.md` にコピー
   （Windows: `C:\Users\<ユーザー名>\.claude\skills\sangaku-yohou\SKILL.md`）
2. コピー先ファイル内の `{{REPO_PATH}}` をクローン先の絶対パス（例: `D:\dev\lab6`）に一括置換
