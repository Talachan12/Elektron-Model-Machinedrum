// Vérifie le patcher web des machines du Machinedrum (docs/md/) contre tools/build.py :
//   node tools/md_web_check.js model-cycles_OS1.13.syx Elektron_SPS1-1UW_OS1.63.syx model-cycles_OS1.13_mod.syx
// Le 3e fichier : la sortie de « build.py -t md-machines --md … » (comparée octet pour octet).
"use strict";
const fs = require("fs"), path = require("path");
global.window = {};
const docs = path.join(__dirname, "..", "docs");
require(path.join(docs, "md", "md-data.js"));
const md = require(path.join(docs, "md", "md.js"));
const [cyc, mdf, ref] = process.argv.slice(2);
const t0 = Date.now();
const r = md.patch(new Uint8Array(fs.readFileSync(cyc)), new Uint8Array(fs.readFileSync(mdf)), window.MD_WEB);
console.log(`  MAIN OS ${r.mainOsSha} (attendu ${window.MD_WEB.mainos_sha256}) en ${Date.now() - t0} ms`);
let ok = r.mainOsSha === window.MD_WEB.mainos_sha256;
if (ref) {
  const same = Buffer.compare(Buffer.from(r.raw), fs.readFileSync(ref)) === 0;
  console.log(`  .syx identique à celui de tools/build.py : ${same ? "oui" : "NON"}`);
  ok = ok && same;
}
let bad = false;
try { md.patch(new Uint8Array(fs.readFileSync(mdf)), new Uint8Array(fs.readFileSync(mdf)), window.MD_WEB); bad = true; }
catch (e) { console.log(`  fichiers inversés refusés : ${e.message}`); }
process.exit(ok && !bad ? 0 : 1);
