# Namima

## これからの定義

Namima は **Music のライト版**ではなく、  
**Public-Friendly Ambient Player** として開発・運用します。

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
human-reviewed Music packet routing. It never stores audio, samples, lyrics, or
raw interaction streams.

Music SYNC:
- Musicの `SYNC` はmetadata-onlyの現在状態共有です。
- namimaは `routing.namima` をsafe moodへ翻訳します。
- `performance_state.mic_follow` がある場合は、息/ハミングを水と空気、手拍子/パルスを水面反応のヒントとして扱います。マイク音声は録音/保存/送信しません。
- 音は `Tap to start` まで開始しません。
- 録音、アップロード、サンプル、歌詞、raw trace保存はしません。
- JSON貼り付けUIは、ローカル開発や別origin時のfallbackです。

