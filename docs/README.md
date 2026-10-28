# Namima

2026-10-28・5つの景色（v14）: 水面・木漏れ日の庭・灯りの部屋・夕景・月あかりを、それぞれ別の形と光で描く。
景色は表の選択欄と「次の景色」で直接切替。再生前も景色だけ選べ、音はTapまで始まらない。
「おまかせ」は押した時に次の景色へ移り、その後28〜42秒で5景色を巡る。進み具合も表示し、手動選択で間隔をリセット。
背景は長辺1600px以下・最大2枚のキャッシュで合成。通常は1.8秒で移り、reduced motionでは即時に切り替わる。
狭幅はdesktop UAでも220粒子・30fps。音は既存のmood APIで1.2秒の滑らかな変化を使い、合成音源は変更しない。
実iPhoneの表示・聴感は未確認。本番PWAでの本人の感想を受けて調整する。

2026-10-28・水面の光（v13候補）: 波の等高線と指の波紋を見やすくし、こだま／変奏は暖色の点と波で描く。
映像切替を表に出し、「ひと休み」で音を停止してタップで再開できる。
景色名は日本語、動きを減らす設定では粒子の漂流を省く。音符・合成・響きの設定はv12と同じ。
画面の開始は手動のまま。実iPhoneの操作・聴感は別途確認し、必須検証後に既存本番へ公開し、PWAでの本人試聴を受けて調整する。

## Current stack role

Namima は **Music のライト版**ではなく、Music Stack の
**Public-Friendly Ambient Player** です。Music / Hazama FM / Band Room
から来た `SYNC` を、family-safe な水面、庭、透明感、soft sleep の mood に
翻訳します。音は必ず `Tap to start` まで始まりません。

### 方向性（不変）

- 家庭で聴ける音作り（過度な刺激を避ける）
- 昼間に流しても違和感が出にくいバランス
- 水面・波・庭・透明感のある空気感
- glitch 音や重い低域寄りの圧を控えめにする

### Music から移植してよいもの

- **recorder 思想**  
  ユーザーの操作や変化を追跡しやすい保存/再現フロー
- **simple AutoMix**  
  シンプルで穏やかな自動ミックス導線
- **safe limiter 方針**  
  音圧と破綻を抑える保護設計
- **reference-driven presets の安全側**  
  参照ドリブンな再現を保ちつつ、過度な破綻処理を避ける

### Music から移植しないもの

- dark glitch 過多
- heavy bass の前面化
- Aphex / Autechre 的な破綻寄りの操作感
- 実験的 pad 操作の優先開発

## 将来像

- Start / Auto / Mood 程度の簡潔な UI
- public pages 向けの公開体験を想定
- **no samples / no dependencies** 方針（必要な体験を自前実装中心で維持）

## Current docs map

- Stack role / local inventory: [namima-inventory-roadmap.md](namima-inventory-roadmap.md)
- namima-lab lineage closure: [namima-lab-harvest-closure.md](namima-lab-harvest-closure.md)
- Mood profile schema: [mood-profile-schema.md](mood-profile-schema.md)
- Mood profiles: [profiles/mood-profiles.json](../profiles/mood-profiles.json)
- Input/output examples: [input-output-example.md](input-output-example.md)
- Ambient interaction contract: [ambient-interaction-contract.md](ambient-interaction-contract.md)
- Ripple interaction design: [ripple-interaction-design.md](ripple-interaction-design.md)
- Ambient listening scorecard: [ambient-listening-scorecard.md](ambient-listening-scorecard.md)
- Safe Auto mood design: [safe-auto-mood-design.md](safe-auto-mood-design.md)
- Session trace recorder design: [session-trace-recorder-design.md](session-trace-recorder-design.md)
- Reference intake template: [namima-reference-intake-template.md](namima-reference-intake-template.md)

Music session mood adapter: `music-session-adapter.js` exposes
`window.NamimaMusicSessionAdapter.translateMusicSessionPacket(packet)` and
`window.namimaAdapter.applyMusicSessionPacket(packet)` for metadata-only,
metadata-only Music packet routing with manual audio start. It never stores audio, samples, lyrics, or
raw interaction streams.

Current stack alignment:
- Hazama FM v172 の `review_cue` は `source_context.hazama_fm` として読み、
  `piano foreground` は透明な evening air、`safe ambient` は water/garden、
  `techno balance` は低刺激な family/water 側へ寄せます。
- `source_context.hazama_fm.conversation` には Hazama FM v172 の抽象的な
  8小節会話役割だけを残します。Namimaは「呼ぶ/返す/間を空ける」の空気を
  読みますが、旋律やコードや音声は受け取りません。
- Band Room の drum-floor handoff は `source_context.source_surface =
  "band_room"` として診断に残しますが、`routing.namima.enabled = false` の
  ままなら Namima は勝手に mood を採用しません。
- Drum Floor / Chill / OpenClaw への戻りリンクを Music SYNC panel に置き、
  PWA standalone でも現在URLと行き先を確認できます。

Music SYNC:
- Musicの `SYNC` はmetadata-onlyの現在状態共有です。
- namimaは `routing.namima` をsafe moodへ翻訳します。
- `performance_state.mic_follow` がある場合は、息/ハミングを水と空気、手拍子/パルスを水面反応のヒントとして扱います。マイク音声は録音/保存/送信しません。
- 音は `Tap to start` まで開始しません。
- 録音、アップロード、サンプル、歌詞、raw trace保存はしません。
- JSON貼り付けUIは、ローカル開発や別origin時のfallbackです。

Diagnostics:
- `window.namimaAdapter.snapshot().stack_alignment`
- `window.NamimaMusicSessionAdapter.last.source_context`

