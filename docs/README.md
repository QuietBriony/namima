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

