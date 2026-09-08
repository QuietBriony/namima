# Offline IDM → Sonar編集パケット

既存の `namima.idm_ambient` の出音を変えずに、同じ生成時点のパートを取り出す
opt-in機能。公開PWAとは接続しないcandidateです。過去のWAVからの音源分離でも、
過去の納品を完全再現できたという判定でもありません。

## 入口

既に承認済みのnumpy / scipy環境がある場合だけ、namima repo rootから実行します。
この機能を使うための新しい依存追加はありません。

```powershell
$env:PYTHONPATH = 'src'
python -m namima.idm_stems --out-dir 'C:\your-existing-audio-folder\new-idm-edit'
```

`C:\your-existing-audio-folder` は自分で確認した保存先に置き換えます。
親folderは既存、出力folderは未使用の絶対パスが必須。既存の空folderも拒否します。
自動Drive探索・upload・再生・Sonar起動・MIDI/device操作はしません。
共有・同期folderを自分で指定した場合は、その既存同期設定に従って同期され得ます。

既定は16小節・96 BPM・idm・seed 174852（43秒、3秒tail込み）。
leadは9小節目、drumsは13小節目からなので、8小節だけでは全パートを確認できません。
`--bars` 1–64 / `--bpm` 40–240 / `--root-degree` 0–8 / `--gain` 0.71–0.95。
48 kHz固定、masterのfadeを収めるためtail込み5秒以上・180秒上限。
これはメモリ使用の上限を設けた短い編集候補用で、
長尺の全stem出力やGPU処理を自動で始めるものではありません。

## 出力と意味

- `01-pad.wav`〜`07-reverb.wav`: pad / lead / lead_echo / sub / drums / texture / reverb。
  元mix係数適用済み。共通gainだけで減衰し、個別正規化しません。
- `08-premaster-reference.wav`: 7partの和。stemと同じgain、比較用。
- `09-master-reference.wav`: 既存rendererと同じmaster。比較用で、stemに重ねません。
- `recipe.json`: config / preset snapshot / source SHA-256 / Python・numpy・scipy版。
- `HANDOFF.md`: パートの役割・Sonarへの手動取込・引き算の試聴案・再実行コマンド。
- `manifest.json`: file hash / format / frame数 / gain / 未判定項目。最後に書く完了マーカー。

全WAVは24-bit PCM・48 kHz・stereo・同じ開始時刻と長さ。stemと08はdual monoです。
7partと和の最大peakを見て、共通gainで最大−6 dBFSへ減衰します（boostなし）。
元の共通HPF・nonlinear glue・fade・RMS/limiter・stereo処理より**前**を取り出すため、
stemの和は09と一致しません。量子化後のstem和と08の誤差許容はmanifestへ記録します。

共有reverbはpad / lead / echo / drumsの送信が印刷済みで、muteやフェーダーに追従しません。
drums内のkick / rim / hat / breakはまだ1bus。MIDI・個別drum・.cwp・圧縮版は出力しません。
この制限を理解して「音声の引き算と構成編集」から始め、音符編集は次工程に分けます。
絶対Hzのnon-12-TETなので、普通のMIDI化を音程が同じ再現と呼ばないでください。

## 検証と境界

```powershell
python -m pytest tests/test_idm_stems.py -q
```

既定master不変（3モード・lead/drumsが鳴る構成）、gainと時刻整列、PCM roundtrip、
既存path拒否、異常configの先行拒否、途中失敗と完了マーカー、hashを検証します。
静的・波形検証はSonar実操作や人の試聴を代替しません。
既存音源、公開PWA、delivery catalogやverdictは更新せず、生成物はGitに追加しません。
失敗した新規folderは検査用に残します。自動削除・上書き再開はしません。
