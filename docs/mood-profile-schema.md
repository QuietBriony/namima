# Mood Profile Schema (Public-Friendly Ambient Player)

## Purpose

Namima は以下を満たすため、**Public-Friendly Ambient Player** として動かす。

- family-safe
- daytime listening
- water-like / garden-like ambience
- soft continuous listening

Music の実験的 IDM / glitch 的方向をそのまま移植せず、
初期は**手入力 mood profile**ベースで進める。

将来は Music 側の安全な `reference/preset` 要素を段階的に取り込む。

## Input profile (mood_id schema)

- `mood_id`: 参照する profile の識別子
- `brightness`: 亮度（例: `low`, `medium`, `medium_high`）
- `warmth`: 温度感（例: `cool`, `warm`, `soft_warm`）
- `water_motion`: 水の動き（例: `low`, `medium`, `high`）
- `garden_air`: 園庭の空気感（例: `low`, `soft`, `open`）
- `rhythm_density`: 脈動/リズム密度（例: `none`, `low`, `medium`）
- `low_end_pressure`: 低域の圧（例: `very_low`, `low`, `medium`）
- `texture_amount`: テクスチャ量（例: `low`, `medium`, `high`）
- `melody_presence`: メロディ要素量（例: `none`, `minimal`, `present`）
- `sleepiness`: 睡眠寄り寄与（例: `low`, `medium`, `high`）
- `family_safe`: 家庭で再生して問題が起きにくいか（`true`推奨）
- `duration_intent`: 再生意図（例: `short`, `loopable`, `continuous`）

## Output ambient feel

- `pad`: 背景パッドの質感
- `water_texture`: 水面や波のテクスチャ
- `air_layer`: 透明感のある空気層
- `soft_pulse`: 低侵襲な脈動
- `melody_fragment`: 最小限のメロディ断片
- `room_space`: 空間系の広がり
- `transition`: profile 変更時の遷移振る舞い
- `density`: 全体密度の目安
- `brightness`: 全体の明るさ
- `loudness_safety`: 音圧上限制御方針

## Safety policy

- no audio files
- no samples
- no dependencies
- no runtime code in this PR
- no harsh glitch
- no heavy low-end pressure
- no dark / violent aesthetic as default
