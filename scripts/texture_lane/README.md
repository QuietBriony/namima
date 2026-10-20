# texture_lane — 285 Hz Drift II の質感層レーン

namima の **Hz 真値の核**（`hazama_release.render_drift(285)` + `master(…, "drift")`・決定論・seed 200285）の下に、
ACE-Step 1.5 で生成した環境音ベッドを **HPF 800 Hz より上だけ**に敷くレーン。生成ベッドには 12 平均律の残留音程が
混ざる（T1 雨は生成直後、A5 = 879 Hz の 1 音がベッドの約半分のエネルギー＝285 格子と 48 cents ずれたハム）ので、
ノッチで抜き、tanh で粒を均してから `namima.texture_layer.layer()` で層ねる。核は一切加工しない。

**2026-10-20 採用（285 Drift II）: T1「雨」ベッド・−24 dB / width 0.5**（seed 285・HPF = `highpass_for(285)` = 800 Hz）。
既存の 285 Drift は差し替えず、「II」として次の波で出す。

- 音源はリポに入れない（namima rule 5）。全スクリプトは出力先を引数で受ける。作業フォルダ `<W>` はリポの外に置く。
- CPU・決定論（numpy / scipy）。GPU を使うのはベッド生成（ACE-Step API）だけ。
- ffmpeg は `namima.deliver.find_ffmpeg`（`NAMIMA_FFMPEG` → PATH → imageio-ffmpeg）。
- 1 時間動画だけ外部の `yt_build.py`（hazama-release/youtube・git 管理外）を使う。Pillow / imageio-ffmpeg が要り、
  `yt_build.py` 自身の固定パス・Windows フォント前提もそのまま（その構成がある PC で回す）。

## 手順（リポ root から）

### 1. ベッド生成（GPU）

```powershell
$env:ACESTEP_API_URL = "http://<ace-step-host>:<port>"   # 必須（コードに既定値なし）
$env:ACESTEP_GPU_LOCK = "<lock file path>"               # 任意: 共有 GPU のロック（未設定ならロックしない）
$env:ACESTEP_GPU_LOCK_SSH = "<user>@<gpu-host>"          # 任意: ロックが GPU 機側にある時（ssh + cmd で作成/削除）
python scripts/texture_lane/ace_textures.py --out <W>/bed-src
```

T1 雨 / T2 テープ風 / T3 海の空気 の 90 s ベッド `<tag>-90s-48kf32.wav`（`acestep-v15-turbo`・seed 285000+i・
lyrics `[inst]`・8 steps・ode・shift 2.4・bpm/key なし）と `ace-textures-manifest.json`。

### 2. 核 + 対照（probe1）

```
python scripts/texture_lane/probe1_layer.py --out <W> --bed <174 で耳承認済みの air ベッド ace-air-altA-60s-48k24.wav>
```

`<W>/285-drift-core-48k24.wav`（以降の全候補が共有する核）と、既定 A_approved（−20 dB / 0.50）・
B_codex（−22 dB / 0.22）の層ね・`measurements-probe1.json`。

### 3. ベッドの衛生チェック

```
python scripts/texture_lane/bed_stats.py <W>/bed-src/ace-T1-rain-leaves-90s-48kf32.wav --condition <W>/bed-src/ace-T1-rain-leaves-cond9.wav --knee-db 9
python scripts/texture_lane/bed_tonal.py <W>/bed-src/ace-T1-rain-leaves-cond9.wav
```

crest / click/min / flatness 800–6k / pulse と、800–6k の残留音程ピークが 285 格子（285 / 528 / 852 の倍音）から何 cents ずれているか。

### 4. 掃除（採用ベッドはこの 3 コール）

```
python scripts/texture_lane/bed_clean.py <W>/bed-src/ace-T1-rain-leaves-90s-48kf32.wav <W>/bed-src/ace-T1-rain-leaves-clean8.wav --prom-db 8
python scripts/texture_lane/bed_clean.py <W>/bed-src/ace-T1-rain-leaves-clean8.wav <W>/bed-src/ace-T1-rain-leaves-clean8n.wav --notch-only 1403.2 2322.0
python scripts/texture_lane/bed_clean.py <W>/bed-src/ace-T1-rain-leaves-clean8n.wav <W>/bed-src/ace-T1-rain-leaves-final.wav --notch-only 1760.0
```

- 1 本目: HPF 800 Hz（8 次 zero-phase）→ 卓越 8 dB 超の音程ピークを自動ノッチ（2 パス・各 ≤ 16 本・−3 dB 幅 ±40 cents。
  T1 は 19 本）→ tanh ソフトクリップ（ベッド RMS +9 dB）。
- 2・3 本目: 核の部分音 1425 / 2287 / 1710 Hz と同じ臨界帯域に残った F6 / D7 / A6 の狙い撃ち。tanh の**後**に、
  24-bit ファイルを挟んで 2 回（この順で採用ベッドと同一バイトになる）。

### 5. 層ね + 計測（probe2）

```
python scripts/texture_lane/probe2_layer.py --out <W> <W>/bed-src/ace-T1-rain-leaves-cond9.wav <W>/bed-src/ace-T2-tape-wind-cond9.wav
python scripts/texture_lane/probe2_layer.py --out <W> --setting C=-24:0.5 --setting D=-26:0.5 <W>/bed-src/ace-T1-rain-leaves-final.wav
```

1 行目は候補比較（既定 A / B）、2 行目が採用設定。`<W>/ace-T1-rain-leaves-final-C-48k24.wav`（+ 90–180 s の
`-clip90s.wav`）と `measurements-probe2.json`（追記型。作り直す時は先に消す）。計測キーは下の判定表。

### 6. 試聴リール

```
python scripts/texture_lane/make_reel.py <W>/reel-wave2-285-v2.m4a "core=<W>/285-drift-core-clip90s.wav" "T1 雨 -26dB=<W>/ace-T1-rain-leaves-final-D-clip90s.wav" "T1 雨 -24dB=<W>/ace-T1-rain-leaves-final-C-clip90s.wav"
```

各クリップの 30 s 目から 25 s・間 1 s・AAC 192k と `.cue.txt`。
（初版は無音ラベル 1 個の使い回しで、2 個目以降の「間」が 1 本目の抜粋 25 s に化けていた。2026-10-20 までに作った
リールは cue の 3 行目以降が実際より早い — 修正済み。）

### 7. 納品 packet

```
python scripts/texture_lane/make_packet.py <W>/ace-T1-rain-leaves-final-C-48k24.wav 2026-10-20_285hz-drift-wave2-rain 285hz-drift-wave2-rain-s200285-9m44s <W>/packet-notes.md --deliver
```

`<W>/packet/<packet>/` に master wav（48 kHz / 24-bit）・iphone m4a・handoff.md（SHA-256 + notes）。`--deliver` で
Drive レーンの `deliveries/<packet>/` へコピー（新規フォルダのみ。Drive が見つからなければ止まる。
`--handoff-dir` / `NAMIMA_HANDOFF_DIR` で指定可）。

### 8. 1 時間動画

```
python scripts/texture_lane/yt_longform.py <W>/packet/2026-10-20_285hz-drift-wave2-rain/285hz-drift-wave2-rain-s200285-9m44s-master.wav 285 drift2 1 --from-master --youtube-dir <hazama-release>/youtube --image <Drift 家族のキービジュアル.png>
```

`--from-master` で 44.1 kHz / 16-bit 化（`hazama_release.write_wav16_441`・TPDF ディザ seed 400000+Hz = 400285）→
`yt_build.loop_audio`（10 s 等パワークロスフェード）で 1 h → still 1 fps + AAC 192k の `285hz-drift2-1h.mp4`。
出力先は `--out`（既定は `--youtube-dir`）。

## 判定ルーブリック（睡眠 Drift: 優しさ > 迫力・本人委任の AI 判定）

関門 1〜4 は 1 つでも落ちたら不採用、5〜8 で順位。`measure()`（probe1 / probe2 の json）のキーで測る。

| # | 観点 | 測り方 | 線 |
|---|---|---|---|
| 1 | 根音が埋もれない | `root_delta_db`（根音 ±350 cents 帯） | \|Δ\| ≤ 0.3 dB（174 承認実績 −0.043） |
| 2 | 低域が潰れない・柔らかい | `low_crest_db_<150` | 核比で悪化しない（Δ ≥ −0.5 dB。初版は絶対値 ≥ 13 dB） |
| 3 | 荒さが増えない | `band_delta_db_vs_core` 2–6k / 6–16k・`pres_crest_db_2k-6k`・`peak` | 帯域上昇 ≤ +3 dB（※）・2–6k クレスト悪化 ≤ +3 dB・peak ≤ 0.70 |
| 4 | 上乗せでなく敷かれている | `bed_rms_rel_core_db`・`bed_minus_core_db`・`exposure` | bed/core ≤ −18 dB・800 Hz 以下にベッド無し・残留音程 ≤ −35 dB（ミックス比。ピーク位置は `bed_tonal.py`） |
| 5 | 単調でない | `centroid_std_hz`・`env_cv_4s` | 核比 +10 % 以上 |
| 6 | 間・空気 | `side_to_mid`・6–16k | side/mid 0.4–0.7・air +1〜+6 dB |
| 7 | iPhone の中域を壊さない | 150–800 / 800–2k の核比 | ±1 dB |
| 8 | ループ感が出ない | ベッド素材長 | ≥ 60 s（2 s クロスフェードは `layer()` が自動） |

verdict 表記は「AI判定（本人委任・基準=睡眠Drift: 優しさ/根音/飽きなさ）」＋本人の言葉があれば原文併記。

※ ルーブリック作成時の帯域 dB は 10·log10 で半分に出ていた（2026-10-20 の監査で 20·log10 に修正。
`spatial.band_energy` は振幅）。上昇量の採否は下の較正で判断した。

## 較正（−24 dB を採った根拠）

7/28 に耳承認された 174 ミックス（air ベッド・−20 dB / width 0.5）を同じ物差しで測ると **2–6 kHz 上昇 ≈ +6.1 dB・
ベッド露出 p99 ≈ −8.0 dB**。−24 dB 設定は **+6.5 dB / p99 −18.2 dB**＝帯域上昇は承認線と同等、露出は 10 dB 内側
（承認線の内側で最も聴こえるレベル）。

- 露出（`exposure`）= 層ね後ベッドの 50 ms RMS ブロックを核の全体 RMS 比 dB で見たもの（max / p99 / median / −18 dB 超の時間率）。
- 採用版: 根音帯 −0.017 dB・800–2k +0.08 / 2–6k +6.54 / 6–16k +3.91 dB・露出 max −15.2 / p99 −18.2 / median −25.3 dB
  （−18 dB 超 0.77 %）・peak 0.384・RMS −18.39 dBFS。
- 3 審査（睡眠設計 / 測定監査 / 成長戦略）は「雨（T1）」で全員一致。レベルは −26 ×2・−20 ×1 に割れ、全員の 2 位だった
  −24 dB を較正で裏付けて採用。

## 開示ルール

核 = 自己合成（namima・決定論・seed で再生成可）。質感層 = **自前の AI 生成素材（ACE-Step）を改変**（HPF・ノッチ・tanh）。
サンプル・外部音源なし。**公開メタデータ（説明文）に必ず両方を書く。** 例:
「芯の音はすべて自己合成。質感の層は自前のAI生成（ACE-Step）を素材として改変。」/
"Core sounds are self-synthesized; the texture layer is adapted from our own AI-generated material (ACE-Step)."

## 納品済み・再現性

- 納品 packet: Drive レーン `AI連携/Music/deliveries/2026-10-20_285hz-drift-wave2-rain/`
  （master wav・iphone m4a・handoff.md に recipe / 計測 / verdict / 聴きどころ）。
- 2026-10-20 に元の作業スクリプトと突き合わせ済み: 手順 4 の 3 コールは採用ベッドと**同一バイト**、手順 8 の
  `--from-master` の 44.1k/16 は YouTube 素材と同一バイト。
- 手順 5 の層ねは納品 master と ±8 LSB（24-bit・≈ −120 dBFS）以内で一致し、計測値は丸め桁で全キー一致
  （exposure 含む）。納品 master はノッチ直後の未量子化ベッドを同じプロセスで層ねたもので、ファイル経由では
  バイト一致しない。
