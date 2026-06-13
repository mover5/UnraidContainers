// Generates icon.png (512x512) with no image libraries — a light-blue
// 4-pointed star on the dark background, matching the app favicon.
import { writeFileSync } from 'node:fs';
import { deflateSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';

const SIZE = 512;
const BG = [0x0b, 0x12, 0x20];
const FG = [0x38, 0xbd, 0xf8];

// 4-pointed star polygon: 8 vertices alternating outer/inner radius.
const cx = SIZE / 2;
const cy = SIZE / 2;
const R = 210;
const r = 64;
const pts = [];
for (let k = 0; k < 8; k++) {
  const a = (-90 + k * 45) * (Math.PI / 180);
  const rad = k % 2 === 0 ? R : r;
  pts.push([cx + rad * Math.cos(a), cy + rad * Math.sin(a)]);
}

function inside(x, y) {
  let win = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const [xi, yi] = pts[i];
    const [xj, yj] = pts[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) win = !win;
  }
  return win;
}

// Build raw RGBA scanlines, each prefixed with a 0 (no filter) byte.
const raw = Buffer.alloc((SIZE * 4 + 1) * SIZE);
let o = 0;
for (let y = 0; y < SIZE; y++) {
  raw[o++] = 0;
  for (let x = 0; x < SIZE; x++) {
    const c = inside(x + 0.5, y + 0.5) ? FG : BG;
    raw[o++] = c[0];
    raw[o++] = c[1];
    raw[o++] = c[2];
    raw[o++] = 255;
  }
}

// CRC32 (PNG chunk checksum).
const crcTable = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});
function crc32(buf) {
  let c = 0xffffffff;
  for (const b of buf) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const typeBuf = Buffer.from(type, 'ascii');
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(Buffer.concat([typeBuf, data])));
  return Buffer.concat([len, typeBuf, data, crc]);
}

const ihdr = Buffer.alloc(13);
ihdr.writeUInt32BE(SIZE, 0);
ihdr.writeUInt32BE(SIZE, 4);
ihdr[8] = 8; // bit depth
ihdr[9] = 6; // color type RGBA
const png = Buffer.concat([
  Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
  chunk('IHDR', ihdr),
  chunk('IDAT', deflateSync(raw, { level: 9 })),
  chunk('IEND', Buffer.alloc(0)),
]);

const out = fileURLToPath(new URL('../icon.png', import.meta.url));
writeFileSync(out, png);
console.log(`Wrote ${out} (${png.length} bytes)`);
