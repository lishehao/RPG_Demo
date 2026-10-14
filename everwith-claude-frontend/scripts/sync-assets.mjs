#!/usr/bin/env node
// Copies the selected, unmodified handoff files into this project and verifies
// every byte against the package's own verification/SHA256SUMS.txt.
//
//   npm run assets:sync -- --from /path/to/Everwith_Claude_Frontend_Handoff_2026-10-13
//   npm run assets:check            (re-hash what was copied; no copying)
//
// Nothing is downloaded, generated or re-encoded. Missing files are recorded
// and the app degrades to static images / text / explicit "unavailable".
import {createHash} from 'node:crypto';
import {existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync, copyFileSync} from 'node:fs';
import {dirname, join, relative, resolve, sep} from 'node:path';
import {fileURLToPath} from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const checkOnly = args.includes('--check');
const fromIndex = args.indexOf('--from');
const from = fromIndex >= 0 ? args[fromIndex + 1] : process.env.EVERWITH_HANDOFF_DIR;
const PUBLIC_ROOT = join(root, 'public', 'handoff');
const VENDOR_ROOT = join(root, 'src', 'vendor', 'cubism-framework');
const LOCK = join(PUBLIC_ROOT, 'ASSET_LOCK.json');

/** Destination policy: browser-served files go to public/handoff/<same rel path>;
 * Cubism Framework TypeScript goes to src/vendor (compiled by Vite, never served raw). */
function destinationFor(rel) {
  if (rel.startsWith('assets/runtime/cubism/Framework/src/')) return join(VENDOR_ROOT, 'src', rel.slice('assets/runtime/cubism/Framework/src/'.length));
  if (rel === 'assets/runtime/cubism/Framework/LICENSE.md') return join(VENDOR_ROOT, 'LICENSE.md');
  return join(PUBLIC_ROOT, rel);
}

// Selected subset. Prefix entries (ending in '/') take every listed file below them.
const SELECTION = [
  // Cubism runtime subset (Core, Framework source, WebGL shaders, original notices)
  'assets/runtime/cubism/',
  // Five frozen Live2D runtimes with every file their model3 references
  'assets/live2d/',
  // Discovery / portrait / scene imagery and existing home preview clips
  'assets/companions/feed/',
  'assets/companions/portraits/',
  'assets/companions/scenes/',
  'assets/companions/game-previews/v1/',
  // Royale: casino scene atlas used by the frozen board, banknote ornament, provenance
  'assets/games/royale/generated/casino-scene-atlas-r7.png',
  'assets/games/royale/generated/fictional-game-token-ornament-20261004.png',
  'assets/games/royale/generated/PROVENANCE.json',
  // Splendor: active art-catalog indices (6,7,11..19), tier backs, gem finishes, salon
  'assets/games/splendor/nobles-a.jpg',
  'assets/games/splendor/nobles-b.jpg',
  'assets/games/splendor/renaissance-tier1-20261007.png',
  'assets/games/splendor/renaissance-tier2-20261007.png',
  'assets/games/splendor/renaissance-tier3-20261007.png',
  'assets/games/splendor/renaissance-tier2-warehouse-round3-20261007.png',
  'assets/games/splendor/renaissance-tier2-ledger-round3-20261007.png',
  'assets/games/splendor/renaissance-tier2-caravan-round3-20261007.png',
  'assets/games/splendor/renaissance-tier3-cathedral-round4-20261007.png',
  'assets/games/splendor/renaissance-tier3-harbor-round4-20261007.png',
  'assets/games/splendor/teal-velour-calm-round4-20261007.png',
  'assets/games/splendor/tier-back-1-20261005.png',
  'assets/games/splendor/tier-back-2-20261005.png',
  'assets/games/splendor/tier-back-3-20261005.png',
  'assets/games/splendor/tier-backs-provenance-20261005.json',
  'assets/games/splendor/gem-diamond-finish-round4-20261007.png',
  'assets/games/splendor/gem-sapphire-finish-round4-20261007.png',
  'assets/games/splendor/gem-gold-finish-round4-20261007.png',
  'assets/games/splendor/gem-emerald-polish-round4-20261007.png',
  'assets/games/splendor/gem-ruby-polish-round4-20261007.png',
  'assets/games/splendor/gem-onyx-polish-round4-20261007.png',
  'assets/games/splendor/backgrounds/salon.png',
  // CABO: default illustration-print/1 catalogue (manifest.json) + zones + felt
  'assets/games/cabo/card-rank-art/manifest.json',
  'assets/games/cabo/card-rank-art/illustration-print-1-zones.json',
  'assets/games/cabo/embedded-surface-1.webp',
  'assets/games/cabo/card-illustration/provenance.json',
  // Frozen pins used at runtime for identity checks
  'verification/MODEL_PINS.json',
];

function sha256(file) { return createHash('sha256').update(readFileSync(file)).digest('hex'); }
function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) out.push(...walk(full)); else out.push(full);
  }
  return out;
}
function rightsIndex(base) {
  const file = join(base, 'verification', 'ASSET_MANIFEST.json');
  if (!existsSync(file)) return new Map();
  const rows = JSON.parse(readFileSync(file, 'utf8'));
  return new Map(rows.map(row => [row.path, {rights: row.rights, status: row.status, source_commit: row.source_commit}]));
}

if (checkOnly) {
  if (!existsSync(LOCK)) { console.error('No ASSET_LOCK.json. Run: npm run assets:sync -- --from <handoff dir>'); process.exit(2); }
  const lock = JSON.parse(readFileSync(LOCK, 'utf8'));
  let bad = 0;
  for (const item of lock.files) {
    const dest = join(root, item.dest);
    if (!existsSync(dest)) { console.error(`MISSING ${item.dest}`); bad++; continue; }
    if (sha256(dest) !== item.sha256) { console.error(`HASH MISMATCH ${item.dest}`); bad++; }
  }
  console.log(JSON.stringify({checked: lock.files.length, problems: bad, missingAtSync: lock.missing.length}, null, 2));
  process.exit(bad ? 1 : 0);
}

if (!from) {
  console.error('Usage: npm run assets:sync -- --from /path/to/Everwith_Claude_Frontend_Handoff_2026-10-13');
  process.exit(2);
}
const base = resolve(from);
const sums = join(base, 'verification', 'SHA256SUMS.txt');
if (!existsSync(sums)) { console.error(`Not a handoff package (missing verification/SHA256SUMS.txt): ${base}`); process.exit(2); }
const expected = new Map(readFileSync(sums, 'utf8').split('\n').filter(Boolean).map(line => {
  const [hash, ...rest] = line.split('  ');
  return [rest.join('  ').trim(), hash.trim()];
}));
const rights = rightsIndex(base);

const wanted = new Set();
// CABO rank art: exactly the 14 ranks + back named by the default catalogue.
const caboManifest = join(base, 'assets', 'games', 'cabo', 'card-rank-art', 'manifest.json');
if (existsSync(caboManifest)) {
  const m = JSON.parse(readFileSync(caboManifest, 'utf8'));
  for (const entry of [...(m.ranks ?? []), m.back].filter(Boolean)) {
    const name = entry.asset?.path?.split('/').pop();
    if (name) wanted.add(`assets/games/cabo/card-rank-art/${name}`);
  }
}
for (const entry of SELECTION) {
  if (entry.endsWith('/')) {
    for (const rel of expected.keys()) if (rel.startsWith(entry)) wanted.add(rel);
    // Files present on disk but absent from the sums list are not trusted.
  } else wanted.add(entry);
}

const files = [], missing = [], mismatched = [];
for (const rel of [...wanted].sort()) {
  const source = join(base, ...rel.split('/'));
  const want = expected.get(rel);
  if (!want) { missing.push({rel, reason: 'not listed in SHA256SUMS'}); continue; }
  if (!existsSync(source)) { missing.push({rel, reason: 'absent in handoff copy'}); continue; }
  const got = sha256(source);
  if (got !== want) { mismatched.push(rel); continue; }
  const dest = destinationFor(rel);
  mkdirSync(dirname(dest), {recursive: true});
  copyFileSync(source, dest);
  if (sha256(dest) !== want) { mismatched.push(rel); continue; }
  const r = rights.get(rel);
  files.push({rel, dest: relative(root, dest).split(sep).join('/'), bytes: statSync(dest).size, sha256: want,
    rights: r?.rights ?? (rel.startsWith('verification/') ? 'handoff verification metadata' : 'see handoff 08_ASSETS_AND_RIGHTS.md'),
    status: r?.status ?? null});
}

mkdirSync(PUBLIC_ROOT, {recursive: true});
const lock = {
  schema: 'everwith-claude-asset-lock-v1',
  source_package: 'Everwith_Claude_Frontend_Handoff_2026-10-13',
  copied_at_utc: new Date().toISOString(),
  policy: 'byte-identical copies verified against the package SHA256SUMS; no resize/re-encode; private user-authorized handoff; commercial/redistribution rights unverified',
  files, missing, mismatched,
};
writeFileSync(LOCK, JSON.stringify(lock, null, 2));
// Small browser-side availability index (paths only, no hashes needed at runtime).
writeFileSync(join(PUBLIC_ROOT, 'available.json'), JSON.stringify({files: files.filter(f => f.dest.startsWith('public/')).map(f => f.rel)}, null, 0));
console.log(JSON.stringify({copied: files.length, bytes: files.reduce((n, f) => n + f.bytes, 0), missing: missing.length, mismatched: mismatched.length}, null, 2));
if (missing.length) console.log('Missing (app will degrade):', missing.map(m => m.rel).join(', '));
if (mismatched.length) { console.error('Hash mismatch, not copied:', mismatched.join(', ')); process.exit(1); }
