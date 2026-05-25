# Organic Pluck Lab Recipe (namima-lab harvest, concrete values)

## 1. Purpose

`docs/namima-lab-harvest-closure.md` で v2 audio が「safely harvested」と総括されたが、
そこには **具体的な PluckSynth / filter / reverb の数値レンジ** が記録されていない。

本 doc はその欠落を埋める。`namima-lab/a-min` (v1) と `namima-lab/a-min-v2` (v2) の
organic-pluck audio recipe を、namima の `ambient-interaction-contract.md` /
`ripple-interaction-design.md` の語彙へ翻訳して、将来の namima 側 runtime 実装者が
ゼロから数値を再発明しなくて済むようにする。

本 doc は **docs-only translation** で、runtime 配線・schema 変更・依存追加・
sample / audio file 追加はしない。BL-019 (Music BACKLOG) の namima-lab → namima 半分。

## 2. Translation posture

`ripple-interaction-design.md` §2 の方針を踏襲する:

- 実装そのもの（式・アルゴリズム・定数・コピー可能な音響挙動）は **runtime には持ち込まない**
- 体験意図と「数値レンジの傾向」だけを記録する
- 具体値は将来の human-reviewed PR で参照するための reference として残す

つまり本 doc は **runtime 仕様ではなく、将来の実装候補値の lookup table** として
位置付ける。runtime 化には別途 human-gate の listening review が必要。

## 3. Source recipes (a-min v1 / v2)

### 3.1 v1 (a-min/audio.js) — foundation

| 要素 | パラメータ | 値 |
|---|---|---|
| Pluck synth | `attackNoise` | 0.7 |
| Pluck synth | `dampening` | 2600 Hz |
| Pluck synth | `resonance` | 0.92 |
| Pluck velocity | base + intensity × span | `0.18 + intensity * 0.72` (cap 0.9) |
| Pluck duration | base + intensity × span | `0.18 + intensity * 0.22` (秒) |
| Pad envelope | attack / decay / sustain / release | 0.8 / 0.25 / 0.7 / 3.4 |
| Lowpass filter | 静止 / energy 全開 | 520 Hz → 520 + 2600 = 3120 Hz |
| Reverb | decay / preDelay / wet 静止 → 全開 | 6.5 s / 0.01 / 0.16 → 0.16 + 0.42 = 0.58 |
| Master gain | 静止 / energy 全開 | 0.72 → 0.72 + 0.28 = 1.00 |
| Scale | (minor pentatonic) | C, D, Eb, G, Ab × 3 octave (oct 3..5) |

特徴: 1 つの PluckSynth + 1 つの PolySynth (pad) のシンプル構成。pluck は
「触ったら鳴る hit」寄り（velocity 0.72 まで上がる）。

### 3.2 v2 (a-min-v2/audio.js) — refined "hint not hit"

| 要素 | パラメータ | 値 |
|---|---|---|
| Pluck synth | `attackNoise` | 0.6 (v1 より柔らかい) |
| Pluck synth | `dampening` | 2800 Hz (v1 より高め＝ 金属感低減) |
| Pluck synth | `resonance` | 0.9 (v1 より少しゆるい) |
| Pluck velocity | base + intensity × span | `0.10 + intensity * 0.55` (cap 0.85) |
| Pluck duration | base + intensity × span | `0.12 + intensity * 0.18` (秒、v1 より短い) |
| Air pad envelope | attack / decay / sustain / release | 1.8 / 0.4 / 0.75 / 5.2 (release 大幅長) |
| Low drone | MonoSynth filterEnv baseFreq / octaves | 60 Hz / 2 oct |
| Lowpass filter | 静止 → energy 全開 | 520 Hz → 520 + 3200 = 3720 Hz |
| Highpass air filter | 静止 → energy 全開 | 280 Hz → 280 + 520 = 800 Hz |
| Reverb | decay / preDelay / wet 静止 → 全開 | 7.8 s / 0.01 / 0.12 → 0.12 + 0.48 = 0.60 |
| Shimmer delay | delayTime / feedback / wet 静止 → 全開 | 8n / 0.25 / 0.05 → 0.05 + 0.22 = 0.27 |
| Chebyshev sat | order 静止 → 全開 | 8 → 8 + 28 = 36 |
| Master gain | 静止 → energy 全開 | 0.70 → 0.70 + 0.30 = 1.00 |
| 初期 chord velocity | (gentle seed) | 0.06 (v1 は 0.08) |
| Air flicker probability | per tap | 0.55 |
| Pad chord duration | seed | 10 秒 (v1 は 8 秒) |

特徴: v1 の単一 pluck から「low drone + air pad + tiny pluck」の 3-layer 構成へ。
pluck velocity が 0.55 max まで下がり、attackNoise / dampening / release も全部
「hint not hit」方向へ refine された。

### 3.3 v3 (a-min-v3/audio.js) — REJECTED for namima

v3 は PluckSynth を捨てて FMSynth + NoiseSynth + BitCrusher + Transport-driven
irregular grid に向かった。`namima-lab-harvest-closure.md` で v3 audio は
**rejected** と確定済み（dark glitch / metallic reactor / dense repeat は namima の
public-friendly ambient と反する）。

本 recipe では v3 を **参照しない**。v3 の数値は organic-pluck lineage には属さない。

## 4. Translation into namima concepts

`ambient-interaction-contract.md` の Internal Concepts に v2 の数値を写像する:

### 4.1 `water_shimmer` (fine surface movement)

v2 の以下が `water_shimmer` の物質に対応:

- shimmer delay (`FeedbackDelay 8n`, feedback 0.25, wet 0.05–0.27)
- reverb wet (0.12–0.60)
- pluck `dampening` 2800 Hz (高めの dampening が「水面の細かい動き」感を出す)

実装時の目安:
- shimmer wet は `ripple_energy` 上昇で 0.05 → 0.27 にゆるやかに ramp
- reverb wet は 0.12 → 0.60 を **0.18 秒** rampTo で（急に切り替えない）

### 4.2 `air_lift` (subtle brightness in air layer)

v2 の以下が `air_lift` に対応:

- highpass `airFilter` frequency 280 → 800 Hz
- air pad release 5.2 s (長く吊る)
- air pad envelope sustain 0.75 (高い sustain で空気層が消えない)

実装時の目安:
- `air_lift` 増加で airFilter cutoff を 280 → 800 Hz に rampTo 0.12 秒
- air pad の release は短くしない（continuous listening 維持）

### 4.3 `melody_fragment_probability` (rare sparse fragments)

v2 の以下が `melody_fragment` の生成則に対応:

- 1 タップごとの air flicker probability 0.55（毎回ではない）
- air flicker は `air.triggerAttackRelease([n, n2], 2.8s, vel*0.18)` （velocity を
  pluck の 18% まで落とした「ほんの気配」）
- pluck 自体も「hint not hit」（velocity 0.55 cap）

実装時の目安:
- `melody_fragment_probability` 0.4–0.6 で 1 タップごとに発生判定
- fragment は 2–3 秒の release を持ち、velocity は ripple_energy × 0.15 程度に絞る
- octave jump / pitch jump 禁止（v2 の 5-note pentatonic + 隣接遷移を維持）

### 4.4 `soft_pulse_visibility` (gentle pulse)

v2 の以下が `soft_pulse_visibility` の baseline に対応:

- 初期 chord velocity 0.06 (v1 の 0.08 より控えめ)
- low drone trigger velocity 0.16 (静かな bed)

実装時の目安:
- `soft_pulse_visibility` ベースラインは 0.06–0.16 の範囲で mood 別に bias
- `family_room` / `soft_sleep` では 0.06 寄り、`water_day` / `garden_morning` で
  0.10 前後

### 4.5 `fade_back_time` (return to baseline)

v2 の以下が `fade_back_time` の物質に対応:

- pad release 3.4 s (v1) / 5.2 s (v2 air)
- pluck duration 0.12–0.30 s (短い transient で fade-back を阻害しない)

実装時の目安:
- `fade_back_time` 3–6 秒。soft_sleep / family_room は 6 秒寄り、water_day は 3–4 秒
- `touch_release` で必ず soft fade に入る (hard cut 禁止 = `ambient-interaction-contract.md` §安全 ceilings)

## 5. Adopted / Deferred / Rejected matrix

| v1/v2 要素 | namima への翻訳ステータス | 備考 |
|---|---|---|
| PluckSynth attackNoise 0.6 / dampening 2800 / resonance 0.9 | **Deferred** | 概念は記録、runtime 配線は未着手 |
| Pluck velocity 0.10 + intensity × 0.55 cap 0.85 | **Deferred** | "hint not hit" 哲学は記録 |
| Air pad release 5.2 s + sustain 0.75 | **Adopted (concept)** | `fade_back_time` / `air_lift` 概念に既に存在 |
| Shimmer delay 8n feedback 0.25 wet 0.05→0.27 | **Deferred** | `water_shimmer` の concrete recipe として記録 |
| Reverb decay 7.8 s wet 0.12→0.60 | **Adopted (concept)** | 「Deeper but still calm space」(closure §Adopted) として既存 |
| Highpass air filter 280→800 Hz | **Deferred** | `air_lift` の concrete recipe として記録 |
| Chebyshev sat order 8→36 | **Rejected** | 「harmonic thickening」は public-friendly ambient で過剰になりうる、家族向け聴感を壊さない low order なら可だが、デフォルトは入れない |
| Low drone MonoSynth + filter Env (baseFreq 60 Hz / 2 oct) | **Rejected** | `heavy low-end pressure` 禁止 (closure §safety) に該当しうる、家族向け baseline には不要 |
| 5-note minor pentatonic scale (C/D/Eb/G/Ab) | **Adopted (concept)** | 隣接遷移 / pitch jump 禁止と整合、scale 自体は mood profile で別途決める |
| Air flicker probability 0.55 per tap | **Deferred** | `melody_fragment_probability` の上限目安として記録 |
| Initial chord velocity 0.06 (gentle seed) | **Adopted (concept)** | `soft_pulse_visibility` baseline と整合 |
| v3 FMSynth / BitCrusher / NoiseSynth / Transport pattern | **Rejected** | closure §Rejected, dark glitch out of scope |

## 6. Runtime boundary

本 doc は **runtime には配線しない**。

- `engine.js` / `index.html` / `style.css` / `music-session-adapter.js` を変更しない
- `docs/schema/mood-profiles.schema.json` を変更しない
- audio file / sample を追加しない
- 依存を追加しない
- 既存の `mood_profile` / `ripple` 挙動を変更しない
- PWA manifest / sw.js を変更しない

将来 runtime PR を立てる場合の前提条件:
1. `namima-lab-harvest-closure.md` §Closure rule に従い、namima-lab はあくまで
   reference / archive として残す（runtime 配線は namima 側でゼロから組む）
2. 本 recipe の値は **そのままコピーせず**、namima の mood profile / safety
   ceilings に再翻訳する（特に Chebyshev / low drone は rejected）
3. listening review (human-gate) で water_day / garden_morning / family_room /
   soft_sleep / transparent_evening の体感差を再確認
4. `ambient-listening-scorecard.md` の評価軸と整合
5. 1 PR = 1 idea で逐次出す（一度に全 recipe を runtime 化しない）

## 7. Future runtime suggestions (non-binding)

実装するなら最小単位の候補:

1. **Step 1**: `water_shimmer` の shimmer delay (8n / fb 0.25 / wet 0.05→0.20) だけを
   ripple 入力に配線。Chebyshev / low drone は **入れない**。listening review。
2. **Step 2**: Step 1 が承認されたら、`air_lift` の highpass filter ramp
   (280→800 Hz) を追加。
3. **Step 3**: `melody_fragment_probability` を pluck で実装。velocity 0.15 cap、
   隣接遷移のみ、octave jump 禁止。
4. **Step 4**: mood profile 別 bias を調整して家庭向け validation を通す。

各 step は別 PR、各 PR は human-gate listening review が必要。

## 8. Related docs

- `docs/namima-lab-harvest-closure.md` — v2 の概念的 harvest 総括
- `docs/ambient-interaction-contract.md` — interaction → ambient concept 写像
- `docs/ripple-interaction-design.md` — public-friendly interaction 設計
- `docs/safe-auto-mood-design.md` — 安全 mood 自動切替
- `docs/ambient-listening-scorecard.md` — listening review 指標
- `docs/schema/mood-profiles.schema.json` — mood profile schema (本 PR では非改変)

source:
- `namima-lab/a-min/audio.js` (v1)
- `namima-lab/a-min-v2/audio.js` (v2)
- `namima-lab/a-min-v3/audio.js` (v3, rejected for organic-pluck lineage)

upstream tracking:
- Music repo `docs/autonomy/BACKLOG.md` BL-019 (namima-lab → namima 半分)
- Music repo `docs/archive-repo-harvest-audit.md` §5 (namima-lab harvest)
- Music repo `docs/namima-lab-safe-ripple-lineage-decision.md` (boundary)
