import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

function text(path) {
  return readFileSync(join(root, path), "utf8");
}

function exists(path) {
  return existsSync(join(root, path));
}

const manifest = JSON.parse(text("manifest.webmanifest"));
assert.equal(manifest.id, "./");
assert.equal(manifest.start_url, "./");
assert.equal(manifest.scope, "./");
assert.equal(manifest.display, "standalone");
assert.ok(manifest.display_override.includes("standalone"));
for (const icon of manifest.icons) {
  assert.ok(exists(icon.src), `missing icon: ${icon.src}`);
}

const html = text("index.html");
assert.match(html, /rel="manifest" href="\.\/manifest\.webmanifest"/);
assert.match(html, /navigator\.serviceWorker\.register\("\.\/sw\.js"\)/);
for (const asset of ["audio.js?v=stack-3", "music-session-adapter.js?v=stack-3", "sketch.js?v=stack-3"]) {
  assert.ok(html.includes(asset), `missing html asset marker: ${asset}`);
}
assert.match(html, /data-share-link/);
assert.match(html, /Hazama FM/);
assert.match(html, /OpenClaw/);

const sw = text("sw.js");
assert.match(sw, /const CACHE_PREFIX = "namima-pwa"/);
assert.match(sw, /const VERSION = `\$\{CACHE_PREFIX\}-v3`/);
for (const asset of ["audio.js?v=stack-3", "music-session-adapter.js?v=stack-3", "sketch.js?v=stack-3"]) {
  assert.ok(sw.includes(`"${asset}"`), `missing sw precache asset: ${asset}`);
}

const precacheBlock = sw.match(/const PRECACHE_URLS = \[([\s\S]*?)\];/);
assert.ok(precacheBlock, "missing PRECACHE_URLS");
for (const [, url] of precacheBlock[1].matchAll(/"([^"]+)"/g)) {
  if (url === "./") continue;
  assert.ok(exists(url.split("?")[0]), `missing precache target: ${url}`);
}

// sw.js carries two cache identifiers that must move in lockstep (see
// AGENTS.md "Cache buster discipline"): the VERSION suffix (namima-pwa-vN)
// and the asset cache-buster query (?v=stack-M). If bumped separately they
// drift and serve stale assets, so assert N === M loudly here.
const versionMatch = sw.match(/const VERSION = `\$\{CACHE_PREFIX\}-v(\d+)`/);
assert.ok(versionMatch, "missing VERSION declaration in sw.js");
const versionNumber = Number(versionMatch[1]);
const bustNumbers = new Set(
  [...sw.matchAll(/\?v=stack-(\d+)/g)].map(([, n]) => Number(n))
);
assert.ok(bustNumbers.size > 0, "missing ?v=stack-N cache-buster in sw.js");
assert.equal(
  bustNumbers.size,
  1,
  `inconsistent ?v=stack-N values in sw.js: ${[...bustNumbers].join(", ")}`
);
const bustNumber = [...bustNumbers][0];
assert.equal(
  versionNumber,
  bustNumber,
  `sw.js cache identifiers drifted: VERSION is namima-pwa-v${versionNumber} ` +
    `but assets use ?v=stack-${bustNumber} — bump both to the same number`
);

const audio = text("audio.js");
const sketch = text("sketch.js");
assert.match(audio, /panic/);
assert.match(audio, /releaseVoices/);
assert.match(sketch, /quietForPageLifecycle/);
assert.match(sketch, /visibilitychange/);
assert.match(sketch, /pagehide/);
assert.match(sketch, /freeze/);

console.log("Namima PWA static contract passed");
