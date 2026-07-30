#!/usr/bin/env node
// Build a design-map (map.md + map.json + metadata.xml) from a Figma `get_metadata` XML dump.
// Images are captured separately by the agent via the Figma desktop MCP (get_screenshot);
// this script parses the metadata tree, picks the screen frames, and prints the screenshot worklist.
// Usage: node export.mjs <figma-url> <metadata-xml-path> [outdir]
//        node export.mjs --selftest

import { readFile, writeFile, mkdir, copyFile } from 'node:fs/promises';
import path from 'node:path';

// Constrained XML -> tree parser for Figma get_metadata output.
// Tags: canvas/section/frame/instance/component/component_set/text/slot; attrs id/name/x/y/width/height.
const TAG = /<(\/?)([a-zA-Z_]+)((?:\s+[\w-]+="[^"]*")*)\s*(\/?)>/g;
const ATTR = /([\w-]+)="([^"]*)"/g;
const unesc = (s) =>
  s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');

function parse(xml) {
  const root = { type: 'ROOT', children: [] };
  const stack = [root];
  let m;
  TAG.lastIndex = 0;
  while ((m = TAG.exec(xml))) {
    const [, close, tag, attrStr, selfClose] = m;
    if (close) { stack.pop(); continue; }
    const attrs = {};
    let a;
    ATTR.lastIndex = 0;
    while ((a = ATTR.exec(attrStr))) attrs[a[1]] = unesc(a[2]);
    const node = {
      type: tag.toUpperCase(),
      id: attrs.id,
      name: attrs.name,
      width: +attrs.width || 0,
      height: +attrs.height || 0,
      children: [],
    };
    stack[stack.length - 1].children.push(node);
    if (!selfClose) stack.push(node);
  }
  return root.children[0]; // the single top node (canvas/section/frame)
}

const CONTAINER = new Set(['CANVAS', 'SECTION']);
const FRAME = new Set(['FRAME', 'COMPONENT', 'COMPONENT_SET', 'INSTANCE']);
// Descend containers; the first frame-like node on each branch IS a screen (don't nest into screens).
const expand = (n) => (CONTAINER.has(n.type) ? n.children.flatMap(expand) : FRAME.has(n.type) ? [n] : []);

function selftest() {
  const xml =
    '<canvas id="0:1" name="Page"><section id="1:1" name="Sec">' +
    '<frame id="2:1" name="A" width="360" height="800"><instance id="3:1" name="Icon" width="24" height="24"/></frame>' +
    '<frame id="2:2" name="B" width="360" height="800"/></section></canvas>';
  const frames = expand(parse(xml));
  console.assert(frames.length === 2, 'expected 2 frames, got ' + frames.length);
  console.assert(frames[0].id === '2:1' && frames[0].name === 'A', 'frame0 mismatch');
  console.assert(frames[1].id === '2:2', 'frame1 mismatch');
  const one = parse('<frame id="9:9" name="Solo" width="1" height="1"/>');
  const oneFrames = FRAME.has(one.type) ? [one] : expand(one);
  console.assert(oneFrames.length === 1 && oneFrames[0].id === '9:9', 'single-frame mismatch');
  console.log('selftest OK');
}

if (process.argv.includes('--selftest')) { selftest(); process.exit(0); }

const [url, xmlPath, dest = '.'] = process.argv.slice(2);
if (!url || !xmlPath) {
  console.error('Usage: node export.mjs <figma-url> <metadata-xml-path> [outdir]');
  process.exit(1);
}

const um = url.match(/figma\.com\/design\/([^/]+)\/([^/?]*)/);
if (!um) throw new Error('Not a figma.com/design URL');
const [, fileKey, fileName] = um;
const nodeId = new URL(url).searchParams.get('node-id')?.replace('-', ':') ?? '';

const xml = await readFile(xmlPath, 'utf8');
const root = parse(xml);
if (!root) throw new Error('No nodes parsed from metadata XML');
const frames = FRAME.has(root.type) ? [root] : expand(root);
if (!frames.length) throw new Error(`No exportable frames under root ${root.type}`);

const outdir = path.join(dest, 'design-map');
await mkdir(outdir, { recursive: true });
await copyFile(xmlPath, path.join(outdir, 'metadata.xml'));

const seen = new Set();
const entries = [];
const worklist = [];
for (const f of frames) {
  let base = (f.name || '').replace(/[^\w.-]+/g, '_').replace(/^_+|_+$/g, '') || f.id.replace(':', '-');
  while (seen.has(base)) base += `_${f.id.replace(':', '-')}`;
  seen.add(base);
  const file = `${base}.png`;
  const link = `https://www.figma.com/design/${fileKey}/${fileName}?node-id=${f.id.replace(':', '-')}`;
  entries.push({ name: f.name, id: f.id, type: f.type, width: f.width, height: f.height, link, image: file });
  worklist.push(`${f.id}\t${file}`);
}

await writeFile(
  path.join(outdir, 'map.json'),
  JSON.stringify({ source: url, fileKey, nodeId, metadata: 'metadata.xml', frames: entries }, null, 2),
);

const md = [
  `# ${decodeURIComponent(fileName)} — ${root.name ?? ''}`.trim(),
  '',
  `Source: ${url}`,
  `Full metadata tree: [metadata.xml](./metadata.xml)`,
  '',
  ...entries.flatMap((e) => [
    `## ${e.name}`,
    '',
    `- Figma: ${e.link}`,
    `- Node: \`${e.id}\` · ${e.type} · ${Math.round(e.width)}×${Math.round(e.height)}`,
    '',
    `![${e.name}](./${e.image})`,
    '',
  ]),
].join('\n');
await writeFile(path.join(outdir, 'map.md'), md);

console.log('FRAMES\t' + entries.length);
for (const w of worklist) console.log(w);
console.error(`${entries.length} frames -> ${outdir}/map.md + map.json (PNGs pending get_screenshot)`);
