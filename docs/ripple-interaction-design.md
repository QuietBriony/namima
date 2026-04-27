# Ripple Interaction Design for Namima

## 1. Purpose

Namima の今後のランタイム実装に向けて、`namima-lab` のインタラクションを基準として以下を固定する。
目的は、実験的な崩しや破壊よりも、**昼間に流せる・家族と共に聴ける・水面や庭のような空気感**を優先する体験基盤を作ること。

固定する要素:

- touch ripple の存在感を演出として扱い、音作りの暴発要因にしない
- 軽い粒子/エネルギーの増減を、安心して継続再生できる範囲に収束する
- タッチ位置から音の色相を移す際に、急な変化ではなく「なだらかな移動」を重視する
- すべての操作は `public-friendly ambient player` の安全方針を守る

## 2. Source harvest from namima-lab

`namima-lab` の設計から、以下の体験意図だけを借用する。

- 空間を指でなでることで、音の密度や揺らぎが変化する感覚
- ripple が粒子的に拡散し、短時間のエネルギー変化として知覚される設計
- 指位置に応じた明るさ/色相の連続変化
- iOS で再生開始時に安全なユーザー導線を取る必要性

harvest する概念:

- touch / pointer input を一時的な ripple source として扱う
- ripple source が particle field の動きや明るさに影響する
- particle energy は時間経過で自然に減衰する
- X 位置は `xNorm` のような正規化値として扱い、穏やかな note / tone selection に使う
- start overlay は初回 gesture で audio context を開き、その後に体験へ入る

実装そのもの（式・アルゴリズム・定数・コピー可能な音響挙動）はこのPRでは持ち込まない。

## 3. Public-friendly interaction goals

- 1回のジェスチャで過剰に崩れない
- 長時間聴取しても疲れにくい
- 家庭環境でも違和感が少ない（音圧・過度な低域・急激なイベントを避ける）
- 水面/庭/透明感を壊さず、曖昧でやわらかい反応に留める
- タッチは「演出」として理解され、主導権は常に利用者側に残る

## 4. Ripple -> ambient energy mapping

Rippleは、`ambient energy`（音の気配強度）へ以下の方式で写像する。

- 中央付近 or やや小さな ripple:
  - 低～中程度の energy
  - パッドの透明感と空気層をわずかに増やす
- 大きめの ripple / 高速な再入力:
  - energy をゆるやかに上げる
  - ただし `low_end_pressure` と `hard transient` は禁止
- rippleが収束するタイミング:
  - 既存の音色を壊すのではなく、`soft fade` で戻す
- 一時的なピークは許容せず、**continuous listening を最優先**する

実装は将来版で、ここでは値レンジの固定をしない。代わりに「急激に上げない」「戻りに時間を持つ」を必須条件として規定する。

Particle energy は音量や低域ブーストではなく、主に以下の「気配」の強弱として扱う。

- water texture の粒立ち
- air layer の明るさ
- soft pulse のわずかな存在感
- melody fragment の発生しやすさ

連続タッチ時も energy は上限で抑え、粒子の運動が派手になっても音響側は家庭向けの穏やかさを維持する。

## 5. X-position -> gentle note selection

X 方向の位置はメロディ断片への寄与として利用し、以下を採用する。

- 左→中央→右で、同じカテゴリ内を滑らかに横方向に遷移
- 一度に飛び飛びに音階を変えず、隣接移動を優先
- メロディは短く、単純で、無理に密度を増やさない
- `melody_fragment` が主役化しない（背景が常に主役）
- 左側は低め/暖かめ、中央は安定、右側は少し明るめの傾向に留める
- 高速な連打やドラッグでも octave jump や急な pitch jump を避ける

ユーザーは触ることで空間の雰囲気を「なぞる」感覚を得ることを目標とし、明確な楽曲演奏の操作に寄せない。

## 6. Mood profile relationship

本デザインは既存 mood profile と次の対応を持つ。

- `water_day` / `transparent_evening`:
  - ripple 速度と水面テクスチャを高めるが、音圧は保守
- `garden_morning` / `family_room`:
  - ゆるい ripple と長い減衰で、透明な空気層を優先
- `soft_sleep`:
  - ripple と X 変化ともに最小振幅で、静かなフェード中心

変換は固定的なアルゴリズムではなく、profile の `input_bias` と `ambient_translation` を参照して調整する方向を想定する。

## 7. iOS safe start behavior

iOS ではユーザー操作起点でのみ音が開始されるため、次を明文化する。

- 初回ページ表示時に自動再生しない
- START などの明示アクションがあるまで待つ
- 初回操作後、短いガイダンス（タップ/ドラッグ開始）を一度だけ提示して状態を確定
- 起動失敗時は再試行導線を静かに提示し、視覚的に過度な強調をしない
- overlay の主目的は decoration ではなく、gesture-bound audio start を明確にすること
- overlay を閉じた後も、音量や energy の初期値は小さく始める

これを満たすと、再生開始時の失敗体験と過負荷操作を避けられる。

## 8. Safety rules

- no hard cut (音の突然切り替えを避ける)
- no harsh glitch
- no heavy low-end pressure
- no dark/violent progression
- no sample-heavy dependency reliance
- no dependency-heavy runtime coupling for interaction state
- any future runtime change must preserve family-safe and daytime continuity goals

## 9. Future runtime boundary

本PRは設計定義のみ。将来実装時の境界:

- 追加実装は `docs/schema/mood-profiles.schema.json` と整合する
- `mood profile` の意図と乖離しない
- `simple AutoMix` 的な自動挙動と `safe limiter` 方針に整合
- 実験的なノイズ/乱れ中心の `Music` 的拡張は後回し

## 10. Next suggested PRs

1. Interaction contract ドキュメントで、touch -> パラメータ写像の中間値レンジ表を追加する
2. 1回タップ/スワイプあたりの期待値（ripple decay time / max rise / max fade）を定義する
3. `docs/README.md` から本設計へのナビゲーションを追加する
