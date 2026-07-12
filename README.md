# sangaku-yohou — 山の上の天気を、山頂の高さで調べるツール

山の名前を入れるだけで、**山頂・稜線の気象予報**（稜線の風・山頂気温・体感温度・凍結高度・
降水・雷リスク・眺望の見込み・登山指数）を表にして返すコマンドラインツールです。

```
python scripts/mountain_weather.py --name 燕岳
```

```
### 日別サマリ
| 日付 | 指数 | 天気 | 眺望(朝) | 山頂気温 | 稜線風max(5-16時) | 降水量 | 降水% | 凍結高度min |
|---|---|---|---|---|---|---|---|---|
| 07/18(土) | B△ | 霧雨(弱) | ◎ | 11〜18℃ | 南西 2.2m/s | 0.6mm | 97% | 5210m |
| 07/19(日) | B△ | 霧雨(弱) | ◎ | 11〜18℃ | 南 4.2m/s | 1.8mm | 83% | 5190m |
```

## 特徴

- **山頂の高さの予報**: 麓の天気予報ではなく、山頂標高を指定して気温・風を取得
- **稜線風**: 地上10m風ではなく、上空の気圧面（850/800/700hPa等）の風を山頂標高で補間。
  「麓は風速2mでも稜線は15m」がちゃんと数字で出ます
- **登山指数 A◎/B△/C✕**: 風・降水・雷（CAPE）の複合判定、安全側（最悪値）採用
- **眺望 ◎/○/△/✕**: 雲の高さと山頂の高さを見比べて判定。雲海チャンスも検出
- **内蔵山岳DB 147座**: 百名山＋人気峰。国土地理院の地名検索・標高データで座標を照合済み。
  DBにない山も地名検索で自動解決、緯度経度の直接指定も可
- **16日先までの見通し** と **気象庁/ECMWF/GFS の3モデル比較**（予報の信頼度確認）
- **HTMLレポート出力**: 色分きの単一HTMLで保存、スマホでもそのまま見られる
- **依存ゼロ**: Python 3 標準ライブラリのみ。APIキー・アカウント登録不要

仕組みの詳しい解説（図解入り・非エンジニア向け）:
**[https://halab18.github.io/sangaku-yohou/docs/how-it-works.html](https://halab18.github.io/sangaku-yohou/docs/how-it-works.html)**
（リポジトリ内の [docs/how-it-works.html](docs/how-it-works.html) をブラウザで開いても同じものが見られます）

## 必要なもの

- Python 3.8 以降（追加パッケージ不要）
- インターネット接続（Open-Meteo / 国土地理院APIへのHTTPSアクセス）

## インストール

```
git clone https://github.com/HALab18/sangaku-yohou.git
cd sangaku-yohou
python scripts/mountain_weather.py --name 富士山
```

gitがない場合は GitHub の「Code → Download ZIP」で展開しても同じです。
`scripts/` と `references/` は同じフォルダ直下に置いたまま使ってください（スクリプトが相対参照）。

## 使い方

```
# 基本: 今日から3日分の詳細 + 週間サマリ
python scripts/mountain_weather.py --name 燕岳

# 日付を指定（例: 週末2日分）
python scripts/mountain_weather.py --name 天狗岳 --date 2026-07-18 --days 2

# 16日間の見通し（「来週登れそうな日は?」）
python scripts/mountain_weather.py --name 谷川岳 --weekly

# 3つの気象モデルを並べて予報の確度を確認
python scripts/mountain_weather.py --name 富士山 --compare-models

# HTMLレポートを保存してブラウザで開く
python scripts/mountain_weather.py --name 燕岳 --html --open

# DBにない山・任意の地点（--elev は山頂標高）
python scripts/mountain_weather.py --lat 36.407 --lon 137.713 --elev 2763 --label 燕岳
```

| オプション | 意味 |
|---|---|
| `--name 山名` | 山名で指定（内蔵DB→地名検索の順で解決） |
| `--select N` | 同名の山が複数あるとき候補一覧から番号で選択 |
| `--date YYYY-MM-DD` | 対象日（省略時は今日から） |
| `--days N` | 詳細表示する日数（既定3） |
| `--weekly` | 16日間の日別見通し |
| `--compare-models` | 気象庁JMA / 欧州ECMWF / 米国GFS の比較表 |
| `--html [PATH]` | HTMLレポート保存（PATH省略時は自動命名） |
| `--open` | 保存したHTMLをブラウザで開く |
| `--lat --lon --elev --label` | 座標で直接指定 |

同名の山（例: 「大山」= 鳥取／丹沢）は候補が表示されるので `--select 1` のように選び直してください。

## 出力の読み方

- **登山指数**: A◎=登山適 / B△=要注意（経験者向き・行程短縮検討） / C✕=不適。
  稜線風10/15m/s、3時間降水1/5mm、雷CAPE 500/1000 J/kg が境目。詳細は
  [references/criteria.md](references/criteria.md)
- **体感温度**: 「風速1m/sで体感−1℃」の登山慣用則。濡れるとさらに下がります
- **眺望(朝)**: 4〜8時の最良値。ご来光・朝焼けの目安。「◎(雲海)」は雲海チャンス
- **凍結高度**: 0℃になる高さ。山頂標高より低いと稜線は雪・着氷の世界
- **雷CAPE**: 雷雨の燃料の量。夏山では午後に上がる日は「早出早着・13時までに樹林帯へ」

## Claude Code スキル連携（任意）

[Claude Code](https://claude.com/claude-code) を使っている場合、「◯◯岳の予報を調べて」と
話しかけるだけでこのツールが自動実行され、AIが表の読み解き付きで答えるようにできます。

1. `skill/SKILL.md` を `~/.claude/skills/sangaku-yohou/SKILL.md` にコピー
   （Windows: `C:\Users\<ユーザー名>\.claude\skills\sangaku-yohou\SKILL.md`）
2. コピーしたファイル内の `{{REPO_PATH}}` をクローン先の絶対パス（例: `D:\dev\sangaku-yohou`）に一括置換

数値の取得・計算はすべて本スクリプト（決定的なコード）が行い、AIは解説だけを担当します。

## トラブルシューティング

- **証明書エラー（CERTIFICATE_VERIFY_FAILED）**: SSL検査を行う社内ネットワークで発生します。
  ネットワーク管理者に確認するか、自宅回線で実行してください
- **プロキシ環境**: 環境変数 `HTTPS_PROXY` を設定してください
- **文字化け**: 出力はUTF-8です。Windowsのコマンドプロンプトでは `chcp 65001` を実行するか、
  PowerShell 7 / Windows Terminal の利用を推奨

## データ出典・利用条件

- 気象データ: [Open-Meteo](https://open-meteo.com/) (CC BY 4.0)。無料APIは**非商用利用向け**です。
  商用利用する場合は Open-Meteo の有料プランを契約してください
- 山岳座標の照合: 国土地理院 地名検索API・標高API（出典: 国土地理院）
- 本ツールのライセンス: [MIT License](LICENSE)

## 免責

本ツールの出力は数値予報に基づく**参考情報**であり、登山の安全を保証するものではありません。
山岳地形では予報誤差が大きく、局地的な突風・雷・視界不良は表現できません。
登山指数・眺望は独自の目安です。**最終判断は必ず最新の公式予報
（[気象庁](https://www.jma.go.jp/)・[ヤマテン](https://i.yamatenki.co.jp/)等）と
現地の状況に基づいて自己責任で行ってください。**
