/* Machinedrum machines patcher: what build.py --md does, in the browser.
 *
 * Port of tools/machines/md/md_os.py (reading the Machinedrum OS: SysEx transport, aPLib section 0, the TRX-B2 and
 * EFM tables) and md_sine.py (the DSP's 32768-point sine recurrence, 48-bit, here with BigInt). The "md" parts of
 * the tweak become "hex" parts, then MCBuilder.build (docs/flasher/builder.js, the port of tools/build.py) builds
 * the .syx. Nothing leaves the browser. tools/md_web_check.js checks it against tools/build.py.
 * Published on GitHub Pages from docs/, with a copy of the Modded-Cycles builder.js next to it.
 */
(function () {
"use strict";

const B = (typeof window !== "undefined" && window.MCBuilder) || (typeof module !== "undefined" && require("./builder.js"));

const CF_BASE = 0x200000;
const TABLES = {                       // address, step in bytes, count (md_os.py)
  pitch: [0x24bd94, 4, 128],
  dec: [0x24bf94 + 0x190, 12, 128],
  hold: [0x24c794 + 0x320, 8, 128],
  dirt: [0x24d794, 4, 128],
  lut: [0x24bf94 + 0x24c, 4, 326],
};
const NAME_AT = 0x24f4b9;
const NAME = "TRXB2PTCHDEC\0RAMPHOLDTICKNOISDIRTDIST";

/* Machinedrum OS image from its .syx: 112-byte messages F0 00 20 3C 02 00 7E, [checksum 2 nibbles][address
 * 6 nibbles][32 words of 16 bits in (2, 7, 7) bits]. */
function mdImage(raw) {
  const chunks = new Map();
  let i = 0;
  while (true) {
    const s = raw.indexOf(0xf0, i);
    if (s < 0) break;
    const e = raw.indexOf(0xf7, s);
    if (e < 0) break;
    i = e + 1;
    const m = raw.subarray(s, e + 1);
    if (m.length !== 112 || m[1] !== 0x00 || m[2] !== 0x20 || m[3] !== 0x3c || m[4] !== 0x02 || m[5] !== 0x00 || m[6] !== 0x7e)
      continue;
    let addr = 0;
    for (let k = 9; k < 15; k++) addr = addr * 16 + m[k];
    const d = new Uint8Array(64);
    for (let g = 15, o = 0; g < 111; g += 3, o += 2) {
      const w = (m[g] << 14) | (m[g + 1] << 7) | m[g + 2];
      d[o] = (w >> 8) & 0xff;
      d[o + 1] = w & 0xff;
    }
    chunks.set(addr, d);
  }
  if (!chunks.size) throw new Error("not a Machinedrum OS file");
  const addrs = [...chunks.keys()];
  const base = Math.min(...addrs), end = Math.max(...addrs) + 64;
  const img = new Uint8Array(end - base);
  for (const [a, d] of chunks) img.set(d, a - base);
  return img;
}

const be32 = (b, o) => ((b[o] << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3]) >>> 0;
const s32 = (v) => v | 0;

function coldfireOs(raw) {
  const img = mdImage(raw);
  const n = be32(img, 0);
  let sum = 0;
  for (let k = 8; k < 8 + n; k++) sum = (sum + img[k]) >>> 0;
  if (sum !== be32(img, 4)) throw new Error("Machinedrum OS: section 0 checksum mismatch");
  return B.aplibDepack(img.subarray(0, 8 + n)).data;
}

/* md_sine.py: s[n+1] = 2 cos(w) s[n] - s[n-1], 48-bit, mpyuu/dmacsu/macsu/dmacss, as the Machinedrum DSP A
 * builds it (P:$100068). */
function sineTable() {
  const M56 = (1n << 56n) - 1n, M48 = (1n << 48n) - 1n;
  const s56 = (v) => { v &= M56; return v >> 55n ? v - (1n << 56n) : v; };
  const s24 = (v) => { v &= 0xffffffn; return v >> 23n ? v - (1n << 24n) : v; };
  const lim48 = (a) => (a > (1n << 47n) - 1n ? (1n << 47n) - 1n : a < -(1n << 47n) ? -(1n << 47n) : a);
  const x1 = 0x7fffffn, x0 = 0xd88586n;
  const hist = [0n, (0x000648n << 24n) | 0x7ed46bn];
  const out = new Int32Array(32768);
  out[1] = 0x648;
  let r1 = 1;
  for (let k = 2; k < 32768; k++) {
    const y = hist[r1];
    r1 ^= 1;
    const y1 = s24(y >> 24n), y0 = y & 0xffffffn;
    let a = (x0 * y0) << 1n;
    a = s56((a >> 24n) + ((s24(x1) * y0) << 1n));
    a = s56(a + ((y1 * x0) << 1n));
    a = s56((a >> 24n) + ((s24(x1) * y1) << 1n));
    a = s56(a << 1n);
    const older = hist[r1];
    a = s56(a - (older >> 47n ? older - (1n << 48n) : older));
    hist[r1] = lim48(a) & M48;
    out[k] = Number(lim48(a) >> 24n);
  }
  return out;
}

/* {name: big-endian bytes} for the "md" parts, from the user's Machinedrum OS (SHA-256 checked). */
function mdParts(raw, expectSha) {
  const sha = B.hex(B.sha256(raw));
  if (expectSha && sha !== expectSha)
    throw new Error("this is not the official Machinedrum UW OS 1.63 file (Elektron_SPS1-1UW_OS1.63.syx)");
  const cf = coldfireOs(raw);
  const at = (va) => va - CF_BASE;
  for (let k = 0; k < NAME.length; k++)
    if (cf[at(NAME_AT) + k] !== NAME.charCodeAt(k)) throw new Error("TRX-B2 not found in this Machinedrum OS");
  const toBytes = (vals) => {
    const b = new Uint8Array(4 * vals.length);
    vals.forEach((v, k) => { b[4 * k] = (v >>> 24) & 0xff; b[4 * k + 1] = (v >>> 16) & 0xff; b[4 * k + 2] = (v >>> 8) & 0xff; b[4 * k + 3] = v & 0xff; });
    return b;
  };
  const parts = {};
  for (const [name, [a, step, n]] of Object.entries(TABLES)) {
    const vals = [];
    for (let k = 0; k < n; k++) vals.push(s32(be32(cf, at(a) + step * k)));
    parts[name] = toBytes(vals);
  }
  parts.sine = toBytes(Array.from(sineTable()));
  return parts;
}

/* The tweak with its "md" parts filled in (a copy). */
function fillTweak(tweak, parts) {
  const t = JSON.parse(JSON.stringify(tweak));
  for (const p of t.append.parts) {
    if (!("md" in p)) continue;
    const b = parts[p.md];
    if (!b || b.length !== p.size) throw new Error(`Machinedrum data ${p.md}: ${b ? b.length : 0} bytes, ${p.size} expected`);
    p.hex = B.hex(b);
    delete p.md;
    delete p.size;
  }
  return t;
}

/* Builds the patched Model:Cycles .syx from the two official files. */
function patch(cyclesRaw, mdRaw, data) {
  const parts = mdParts(mdRaw, data.md_sha256);
  const tweak = fillTweak(data.tweak, parts);
  return B.build(cyclesRaw, data.device, [tweak], { expectMainOsSha: data.mainos_sha256 });
}

const API = { mdImage, coldfireOs, sineTable, mdParts, fillTweak, patch };
if (typeof module !== "undefined" && module.exports) module.exports = API;
if (typeof window !== "undefined") window.MDPatch = API;
})();
