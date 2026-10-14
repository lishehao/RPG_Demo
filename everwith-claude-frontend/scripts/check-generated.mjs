#!/usr/bin/env node
// Verifies the user-provided generated images (GPT batch v2-batch-01) that ship in
// public/generated/batch-01 against docs/GENERATED_ASSETS.json:
//   - every listed derivative exists with the recorded sha256 and size, nothing unlisted is served;
//   - every `/generated/batch-01/<file>` written in src/ or index.html (literal or `${GEN}/<file>`) is listed;
//   - the id families picked at runtime (stage backdrops, work covers, persona avatars) are complete.
// Rights of these images: 用户经 GPT 生成并提供；商用/再分发权未核实 (not part of the handoff package).
import {createHash} from 'node:crypto';
import {existsSync, readdirSync, readFileSync, statSync} from 'node:fs';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const doc = JSON.parse(readFileSync(join(root, 'docs', 'GENERATED_ASSETS.json'), 'utf8'));
const problems = [];
const listed = new Map(doc.assets.map(a => [a.derivative.url.replace('/generated/batch-01/', ''), a]));

for (const [name, a] of listed) {
  const file = join(root, a.derivative.path);
  if (!existsSync(file)) { problems.push({file: a.derivative.path, problem: 'missing'}); continue; }
  const bytes = readFileSync(file);
  const sha = createHash('sha256').update(bytes).digest('hex');
  if (sha !== a.derivative.sha256) problems.push({file: a.derivative.path, problem: 'sha256 mismatch'});
  if (bytes.length !== a.derivative.bytes) problems.push({file: a.derivative.path, problem: 'size mismatch'});
  if (!a.original?.sha256 || !a.original?.file) problems.push({file: name, problem: 'no original recorded'});
}
const servedDir = join(root, 'public', 'generated', 'batch-01');
for (const name of existsSync(servedDir) ? readdirSync(servedDir) : []) if (!listed.has(name)) problems.push({file: `public/generated/batch-01/${name}`, problem: 'not listed in docs/GENERATED_ASSETS.json'});

const files = [join(root, 'index.html')];
(function walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) { if (name !== 'vendor') walk(p); }
    else if (/\.(ts|tsx|css)$/.test(name)) files.push(p);
  }
})(join(root, 'src'));
const refs = new Map();
for (const f of files) {
  const text = readFileSync(f, 'utf8');
  const rel = f.slice(root.length + 1);
  for (const m of text.matchAll(/\/generated\/batch-01\/([A-Za-z0-9_.-]+\.(?:webp|png))/g)) refs.set(m[1], [...new Set([...(refs.get(m[1]) ?? []), rel])]);
  if (/const\s+GEN\s*=\s*'\/generated\/batch-01'/.test(text) || /from '[./]*art\/generated'/.test(text)) {
    for (const m of text.matchAll(/\$\{GEN\}\/([A-Za-z0-9_.-]+\.(?:webp|png))/g)) refs.set(m[1], [...new Set([...(refs.get(m[1]) ?? []), rel])]);
  }
}
for (const [name, from] of refs) if (!listed.has(name)) problems.push({file: name, problem: 'referenced but not listed', from});

const families = [
  ...['arthur', 'lena', 'marcus', 'nora', 'iris', 'generic'].map(k => `backdrop-${k}.webp`),
  ...[1, 2, 3, 4, 5, 6].map(i => `work-cover-0${i}.webp`),
  ...[1, 2, 3, 4, 5, 6, 7, 8].map(i => `persona-avatar-0${i}.webp`),
];
for (const name of families) if (!listed.has(name)) problems.push({file: name, problem: 'runtime id family incomplete'});

console.log(JSON.stringify({batch: doc.batch, rights: doc.rights, derivatives: listed.size, staticRefs: refs.size, runtimeFamilies: families.length, problems}, null, 2));
process.exit(problems.length ? 1 : 0);
