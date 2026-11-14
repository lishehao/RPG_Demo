#!/usr/bin/env node
// Finds every `/handoff/...` asset path written in src/ — plain literals and template
// strings built from per-file constants such as `const P = '/handoff/assets/...'` — and
// verifies each file exists in public/handoff (copied by `npm run assets:sync`).
// Paths assembled from data at runtime (Live2D model3 references, CABO ranks from the
// manifest) are verified by the sync script itself.
import {existsSync, readdirSync, readFileSync, statSync} from 'node:fs';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const files = [];
(function walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) { if (name !== 'vendor') walk(p); }
    else if (/\.(ts|tsx|css)$/.test(name)) files.push(p);
  }
})(join(root, 'src'));

const EXT = '(?:png|jpe?g|webp|mp4|json|js|moc3)';
const refs = new Map();
const add = (rel, file) => refs.set(rel, [...new Set([...(refs.get(rel) ?? []), file.slice(root.length + 1)])]);
for (const f of files) {
  const text = readFileSync(f, 'utf8');
  for (const m of text.matchAll(new RegExp(`/handoff/(assets/[A-Za-z0-9_\\-./]+\\.${EXT})(?![A-Za-z0-9_])`, 'g'))) add(m[1], f);
  // Per-file directory constants, e.g. const V = '/handoff/assets/companions/game-previews/v1'
  const consts = new Map([...text.matchAll(/(?:export\s+)?const\s+([A-Z_][A-Z0-9_]*)\s*=\s*['`]\/handoff\/([^'`$]+?)\/?['`]/g)].map(m => [m[1], m[2]]));
  consts.set('GAME_ASSETS', 'assets/games');
  for (const m of text.matchAll(new RegExp(`\\$\\{([A-Z_][A-Z0-9_]*)\\}/([A-Za-z0-9_\\-./]+\\.${EXT})(?![A-Za-z0-9_])`, 'g'))) {
    const base = consts.get(m[1]) ?? (m[1] === 'DIR' ? 'assets/games/splendor' : m[1] === 'ART_DIR' ? 'assets/games/cabo/card-rank-art' : null);
    if (base) add(`${base}/${m[2]}`, f);
  }
}
const missing = [...refs.keys()].filter(rel => !existsSync(join(root, 'public', 'handoff', rel)));
console.log(JSON.stringify({checkedRefs: refs.size, missing: missing.map(rel => ({rel, from: refs.get(rel)}))}, null, 2));
process.exit(missing.length ? 1 : 0);
