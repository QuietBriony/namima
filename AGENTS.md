# AGENTS.md — namima repo operating contract

このリポを触る agent (claude code / codex / 他) が **最初に読む** namima 固有ルール。
music-stack 全体の自走開発エンジンは `Music/docs/autonomy/` にある。

---

## この repo の役割

namima は music-stack の **active な public-friendly ambient (visual) player**。
daytime / family-safe / water / garden / soft continuous listening を担当する。

所有しているもの:

- safe mood translation（Music / Hazama FM / Band Room の状態 → 低刺激 mood）
- ambient profiles（`profiles/mood-profiles.json`）
- user-gesture start（人間の `Tap to start` まで音を出さない）
- metadata-only な Music SYNC translation

Music のライト版ではなく、namima-lab の dark-chaos prototype でもない。

---

## Hard rules（絶対守る）

namima 固有の境界:

1. **dark glitch / heavy bass / stage groove assumptions を入れない。**
   過度な刺激・低域圧・stage 前提は public-friendly な性格を壊す。
2. **namima-lab の runtime code を blind copy しない。** namima-lab は
   lineage / harvest-only。設計を読んで判断したうえで自前実装する。
3. **Music SYNC は metadata-only。auto-start しない。**
   SYNC packet から音源・サンプル・raw stream を受け取らず、人間の
   `Tap to start` まで一切音を出さない。
4. **public-friendly・family-safe を保つ。** 全変更はこの方向性に照らす。

共通ルール:

5. 音源・サンプル・歌詞を repo に追加しない（音は自前合成）。
6. dependency を勝手に足さない（no samples / no dependencies 方針）。
7. GitHub Actions を勝手に足さない。
8. archive / delete / settings 操作はしない（要・別承認）。

main runtime ファイル（変更は慎重に・人間レビュー前提）:
`sketch.js`（p5.js visuals）/ `audio.js`（WebAudio + Tone.js）/
`music-session-adapter.js`（metadata-only SYNC translation）/ `sw.js`。

tech stack: static PWA — p5.js（visuals）+ WebAudio / Tone.js、CDN ロード。

---

## Integrity gate

commit 前に repo root から以下を実行し、**すべて 0 終了**を確認する:

```bash
node scripts/check-mood-profiles.mjs
node scripts/check-music-session-adapter.mjs
node scripts/check-pwa-static.mjs
```

5 repo 一括検証は Music repo root の `node scripts/stack-check.mjs`。
`0 BAD` が commit の前提。BAD があれば commit せず原因解決。

---

## Cache buster discipline

`sw.js` の cache version 変数は `VERSION`（`CACHE_PREFIX = "namima-pwa"` +
`-vN`、現在 `namima-pwa-v3`）。runtime asset は `?v=stack-N` 形式。

UI / runtime（`index.html` / `sketch.js` / `audio.js` /
`music-session-adapter.js`）を変えたら **2 箇所を同期 bump**:

1. `sw.js` の `const VERSION` を `namima-pwa-v(N+1)` へ。
2. `index.html` の `?v=stack-N` と `sw.js` の `PRECACHE_URLS` 内
   `?v=stack-N` を同じ番号へ揃える。

bump 後に `node scripts/check-pwa-static.mjs` で整合を確認する。

---

## Branch & PR convention

| 状況 | 推奨 |
|---|---|
| docs only | main 直 push 可 |
| 非 runtime コード（scripts / profiles など） | feature branch + PR |
| runtime（sketch.js / audio.js / adapter / sw.js）・音・mood を変える | feature branch + PR + 人間レビュー |

作業前に **必ず `git pull --ff-only origin main`** で最新化する。
強制 push（`--force`）は禁止。

---

## Autonomous development

自走開発の入口 / 待ち行列 / 記録は `Music/docs/autonomy/`:

- 構造マップ: `Music/docs/autonomy/STACK-INDEX.md`（最初に読む）
- 作業待ち行列: `Music/docs/autonomy/BACKLOG.md`
- セッション台帳: `Music/docs/autonomy/SESSION-LEDGER.md`
- 作業フロー: `Music/docs/autonomy/AUTONOMOUS-RUN.md`

自律ランの安全上限:

- ✅ docs / BACKLOG / SESSION-LEDGER の整備 — main 直 push 可
- ✅ 非 runtime コード — feature branch + PR まで（merge は人間）
- ❌ runtime（sketch.js / audio.js / adapter / sw.js）・音・mood — 人間レビュー必須
- ❌ 無人 merge、GitHub Actions 追加、dependency 追加、archive / delete 操作

詳細は `Music/docs/autonomy/AUTONOMOUS-RUN.md`。
