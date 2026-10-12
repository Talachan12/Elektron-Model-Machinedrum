/* Browser smoke test (jsdom) of the web flasher: loads the real page and its scripts,
 * fakes Web MIDI, and walks through the 4 steps (choose, OS file, connect over USB, flash).
 * The fake Model:Cycles answers the Elektron Transfer protocol (fast method) with its own
 * decoder and zlib's CRC, and keeps every byte it is sent, to compare with the firmware.
 * Run through tools/webflash_smoke.sh (installs jsdom in a temp folder).
 *   node tools/webflash_smoke.js <synth_dir> [model-cycles_OS1.13.syx] [model-samples_OS1.13.syx] [Syntakt_OS1.42.syx or 1.41]
 * The optional official files are told apart by their names. The Model:Cycles OS checks each
 * combination of the REF_MAINOS sample against its reference hash, and each mod against REF_MODS
 * (app.js, notes/49; the real Syntakt engines need the Syntakt OS too); with the Model:Samples OS,
 * the "Samples OS" tab and the Mods tab on a Model:Samples are checked end to end (REF_SAMPLES_ON_CYCLES,
 * tools/mods_for_samples.py); with the Syntakt OS, the
 * Syntakt engines flow is. */
const fs = require("fs");
const path = require("path");
const zlib = require("zlib");
const { pathToFileURL } = require("url");
const { JSDOM, VirtualConsole } = require("jsdom");

const FLASH = path.join(__dirname, "..", "docs", "flasher");
const SYNTH = process.argv[2];
const REAL = process.argv.slice(3);
const REAL_ST = REAL.find((f) => /syntakt/i.test(path.basename(f)));
const ST_NAME = REAL_ST ? path.basename(REAL_ST) : "Syntakt_OS1.42.syx";
const ST_VERSION = (/OS(\d+\.\d+)/.exec(ST_NAME) || [])[1];   // "1.42" or "1.41": both official, same engines
const REAL_SMP = REAL.find((f) => /samples/i.test(path.basename(f)));
const REAL_MD = REAL.find((f) => /SPS1|machinedrum/i.test(path.basename(f)));
const REAL_OS = REAL.find((f) => f !== REAL_ST && f !== REAL_SMP && f !== REAL_MD);
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
// SMOKE_SHARD=k/n (tools/webflash_smoke.sh with SMOKE_JOBS=n): part k of the combinations of section 6; the other
// sections run in part 0 only; each part writes what it built to SMOKE_SEEN and the script checks the coverage
const [SHARD_K, SHARD_N] = (process.env.SMOKE_SHARD || "0/1").split("/").map(Number);
const MAIN = SHARD_K === 0;
// Syntakt engine combinations offered by the page: tweak id -> engine codes (tweaks.js)
const engineCombos = (w) => Object.fromEntries(w.MC_TWEAKS.features.find((f) => f.engines).combos.map((c) => [c.id, c.engines]));

// Tick exactly the given Syntakt engines (the card is turned on first; ticking before unticking
// never empties the list, which would turn the card off).
async function pickEngines(doc, codes) {
  if (!doc.getElementById("feat-syntakt").checked) { doc.getElementById("feat-syntakt").click(); await wait(5); }
  for (const want of [true, false]) {
    for (const cb of [...doc.querySelectorAll('input[name="eng-syntakt"]')].map((x) => x.value)) {
      const box = doc.getElementById("eng-" + cb);                 // re-query: the cards are re-rendered
      if (codes.includes(cb) === want && box.checked !== want) { box.click(); await wait(5); }
    }
  }
}

// The cards to tick for a REF_MAINOS key (tweak ids joined with "+"): tweak id -> its card and the choice in it (a variant,
// or the Syntakt engines of a combination, alone or with Model-TG), including the tweak a card takes with another one ("with").
function cardsOf(w, key) {
  const own = {}, feats = w.MC_TWEAKS.features;
  for (const f of feats) {
    if (f.engines) for (const c of f.combos) {
      own[c.id] = own[c.tg] = { f, engines: c.engines };
      for (const g of feats.filter((x) => x.joins === f.id && c[x.id]))   // MACRO with the engines (notes/50): both cards
        own[c[g.id].id] = own[c[g.id].tg] = { f, engines: c.engines, also: g };
    }
    else for (const v of f.variants) own[v.id] = { f, variant: v.id };
  }
  for (const f of feats)
    for (const alt of Object.values(f.with || {})) if (!own[alt]) own[alt] = f.engines ? { f } : { f, variant: f.variants[0].id };
  const sel = new Map();
  for (const id of key.split("+")) {
    sel.set(own[id].f.id, own[id]);
    if (own[id].also) sel.set(own[id].also.id, { f: own[id].also, variant: own[id].also.variants[0].id });
  }
  return sel;
}

// Tick exactly the cards of a key (off first: a card held by another one is locked until that one goes off), then the
// variant or the engines of each, and wait for the build.
async function tickKey(w, doc, key) {
  const sel = cardsOf(w, key);
  for (let round = 0; round < 3; round++) {
    for (const want of [false, true])
      for (const f of w.MC_TWEAKS.features) {
        const cb = doc.getElementById("feat-" + f.id);       // re-query: the cards are re-rendered
        if (sel.has(f.id) === want && cb.checked !== want && !cb.disabled) { cb.click(); await wait(5); }
      }
    for (const [id, o] of sel) {
      if (o.engines) await pickEngines(doc, o.engines);
      else if (o.variant) {
        const r = doc.querySelector(`input[name="var-${id}"][value="${o.variant}"]`);
        if (r && !r.checked) { r.click(); await wait(5); }
      }
    }
    await settle(w);
    if (w.MCFlasherApp.state.buildKey === key) return;
  }
}

// Elektron Transfer protocol, written apart from flasher.js (Elektroid's packing: a byte with the
// high bits of the next 7, first one in bit 6).
const XHEAD = [0xf0, 0x00, 0x20, 0x3c, 0x10, 0x00];
function unpack(src) {
  const out = [];
  for (let i = 0; i < src.length; i += 8)
    for (let k = 1; k < 8 && i + k < src.length; k++) out.push(src[i + k] | ((src[i] << k) & 0x80));
  return Uint8Array.from(out);
}
function pack(src) {
  const out = [];
  for (let j = 0; j < src.length; j += 7) {
    const grp = Array.from(src.slice(j, j + 7));
    out.push(grp.reduce((hi, b, k) => hi | ((b >> 7) << (6 - k)), 0), ...grp.map((b) => b & 0x7f));
  }
  return Uint8Array.from([...XHEAD, ...out, 0xf7]);
}
const be = (m, o) => ((m[o] << 24) | (m[o + 1] << 16) | (m[o + 2] << 8) | m[o + 3]) >>> 0;
const cstr = (str) => [...Buffer.from(str, "latin1"), 0];

// A Model:Cycles on USB: answers ping, version, OS upgrade start and blocks like the real one
// (src/connectors/elektron.c), and records what it receives.
function fakeDevice(opts, reply) {
  const dev = Object.assign({ id: 27, name: "Model Cycles", version: "1.13", startStatus: 0, writeError: -1, silent: false,
    pings: 0, starts: 0, blocks: 0, received: null, size: 0, next: 0, bad: [] }, opts);
  dev.handle = (d) => {
    if (d.length < 8 || XHEAD.some((b, k) => d[k] !== b)) return;           // not for the Transfer protocol
    const m = unpack(d.subarray(6, d.length - 1));
    const head = [0, 0, m[0], m[1], m[4] | 0x80];
    let r = null;
    if (m[4] === 0x01) { dev.pings++; r = [...head, dev.id, 1, 0, ...cstr(dev.name)]; }
    else if (m[4] === 0x02) r = [...head, 0, 0, 0, 0, 0, ...cstr(dev.version)];
    else if (m[4] === 0x50) {
      dev.starts++;
      dev.size = m[5] | (m[6] << 8) | (m[7] << 16) | (m[8] << 24);      // little-endian, as Elektroid's memcpy
      if (Buffer.from(m.subarray(9, 16)).toString("latin1") !== "sysex\0\x01") dev.bad.push("start tail");
      dev.received = new Uint8Array(dev.size); dev.next = 0; dev.blocks = 0;
      r = [...head, dev.startStatus, ...(dev.startStatus ? cstr("No space") : [0])];
    } else if (m[4] === 0x51) {
      const crc = be(m, 5), len = be(m, 9), off = be(m, 13), data = m.subarray(17);
      if (data.length !== len || off !== dev.next || len > 0x800 || crc !== zlib.crc32(data, 0xffffffff) >>> 0)
        dev.bad.push(`block ${dev.blocks}: len ${len}/${data.length}, offset ${off}/${dev.next}`);
      dev.received.set(data, off);
      dev.next = off + len;
      const op = dev.blocks === dev.writeError ? 2 : dev.next >= dev.size ? 1 : 0;
      dev.blocks++;
      r = [...head, 0, 0, 0, 0, op];
    }
    if (r && !dev.silent) setTimeout(() => reply(pack(r)), 1);
  };
  return dev;
}

async function load({ midi = true, ports = true, inputs = true, busy = false, secure = true, lang = "en", devName = "Elektron Model:Cycles", device = {} } = {}) {
  const errors = [];
  const vc = new VirtualConsole();
  vc.on("jsdomError", (e) => errors.push("jsdomError: " + ((e.detail && e.detail.message) || e.message || e)));
  const sent = [];
  const listeners = new Set();
  const dev = fakeDevice(device, (data) => listeners.forEach((f) => f({ data })));
  let access = null, devOut = null, devIn = null;
  const html = fs.readFileSync(path.join(FLASH, "index.html"), "utf8");
  const dom = new JSDOM(html, {
    url: pathToFileURL(path.join(FLASH, "index.html")).href,
    runScripts: "dangerously", resources: "usable", virtualConsole: vc,
    beforeParse(window) {
      Object.defineProperty(window, "isSecureContext", { value: secure, configurable: true });
      Object.defineProperty(window.navigator, "language", { value: lang, configurable: true });
      window.addEventListener("error", (e) => errors.push("window.onerror: " + ((e.error && e.error.message) || e.message)));
      window.addEventListener("unhandledrejection", (e) => errors.push("unhandled: " + ((e.reason && e.reason.message) || e.reason)));
      if (midi) {
        const outputs = new Map(), ins = new Map();
        if (ports) {
          devOut = { id: "dev", name: devName, manufacturer: "Elektron", state: "connected",
            send: (d) => { sent.push(d.length); dev.handle(d); }, open: () => Promise.resolve(), close: () => Promise.resolve() };
          outputs.set("dev", devOut);
          outputs.set("iface", { id: "iface", name: "USB MIDI Interface", manufacturer: "Acme", send: (d) => sent.push(d.length) });
          devIn = { id: "dev-in", name: devName, manufacturer: "Elektron", state: "connected",
            open: () => (busy ? Promise.reject(new Error("InvalidAccessError: port in use")) : Promise.resolve()),
            close: () => Promise.resolve(), addEventListener: (t, f) => listeners.add(f), removeEventListener: (t, f) => listeners.delete(f) };
          if (inputs) ins.set("dev-in", devIn);
        }
        access = { outputs, inputs: ins, onstatechange: null };
        window.navigator.requestMIDIAccess = () => Promise.resolve(access);
      }
      window.URL.createObjectURL = () => "blob:x";
      window.URL.revokeObjectURL = () => {};
    },
  });
  await wait(300);
  // tweaks.js fait plus d'1 Mo : sur une machine occupée, les scripts peuvent mettre plus de 300 ms à se charger
  for (let i = 0; i < 200 && !(dom.window.MCFlasherApp && dom.window.MC_TWEAKS && dom.window.MCBuilder); i++) await wait(50);
  return { dom, w: dom.window, doc: dom.window.document, errors, sent, dev, listeners,
    access: () => access, devOut: () => devOut, devIn: () => devIn };
}

// No pause between blocks (50 ms on the real machine): a 2.5 MB file goes through in a few seconds.
function noRest(w) {
  const orig = w.MCFlasher.upgradeFast;
  w.MCFlasher.upgradeFast = (session, raw, opts) => orig(session, raw, Object.assign({}, opts, { restMs: 0 }));
}
const same = (a, b) => !!a && !!b && a.length === b.length && Buffer.compare(Buffer.from(a), Buffer.from(b)) === 0;
async function untilSent(w, ms = 60000) {
  for (let i = 0; i < ms / 50 && w.MCFlasherApp.state.sending; i++) await wait(50);
}

const text = (doc, id) => doc.getElementById(id).textContent;
// text of the elements a selector picks (the Details drawers are always in the page: scope what a check reads)
const textOf = (doc, sel) => [...doc.querySelectorAll(sel)].map((e) => e.textContent).join(" ");
async function settle(w) {
  for (let i = 0; i < 200 && w.MCFlasherApp.state.building; i++) await wait(50);
  await wait(60);
}

async function main() {
  let fail = 0;
  const check = (cond, msg) => { console.log((cond ? "  ok  " : "  FAIL ") + msg); if (!cond) fail++; };

  // 1. Page loads cleanly, everything is wired
  if (MAIN) {
    const { w, doc, errors } = await load();
    check(errors.length === 0, "loads without JS error " + (errors.length ? JSON.stringify(errors) : ""));
    check(typeof w.MCBuilder === "object" && typeof w.MCFlasher === "object", "MCBuilder + MCFlasher present");
    const ids = w.MC_TWEAKS.tweaks.map((x) => x.id);
    const nEng = w.MC_TWEAKS.features.find((f) => f.engines).engines.length;
    check(ids.slice(0, 24).join() === "6ch-usbup,model-tg,model-tg-st,sample-preview,sample-preview-st,latching-mute,trig-preview,browser-scroll,trig-hold,arp,tempo-max,boot-anim,multiline-browser,level-pan-values,trigless-dim,midi-both,midi-live-both,macro,macro-tg,chord-keys,track-filter,lfo-plus,md-machines,syntakt-sd"
      && ids.length === 23 + 4 * ((1 << nEng) - 1) && ids.includes("md-machines") && ids.includes("syntakt-sd-cp") && ids.includes("syntakt-tg-sd-cp-toy-bits")
      && ids.includes("syntakt-sd-macro") && ids.includes("syntakt-tg-sd-cp-toy-bits-swarm-macro")
      && ids.includes("arp") && !ids.some((x) => /exact|snare|multiout/.test(x)) && w.MC_TWEAKS.features.length === 21,
      `MC_TWEAKS: only USB-friendly tweaks, one tweak per choice of the ${nEng} Syntakt engines (no SNARE replacement), alone and with Model-TG, with and without MACRO: ${ids.length} tweaks`);
    check(/build \d{4}-/.test(text(doc, "build-stamp")), "version stamp shown");
    const srcs = [...doc.querySelectorAll("script[src]")].map((x) => x.getAttribute("src"));
    check(["builder.js", "md.js", "tweaks.js", "flasher.js", "app.js"].every((f) => srcs.some((x) => x.startsWith(f + "?")))
      && srcs.every((x) => x.endsWith("?v=" + w.MC_BUILD)), "scripts loaded with ?v=<build> (no stale cache): " + srcs.join());
    check(doc.getElementById("compat").hidden, "no compatibility banner in a good browser");
    // display order: by section (Packs, Sounds & machines, Sequencer, Live playing, Screen & browsing, USB & MIDI),
    // FEATURES order inside a section; the build keeps FEATURES order (checked in 1b)
    const feats = [...doc.querySelectorAll("#features input[type=checkbox]")].map((c) => c.id);
    check(feats.join() === "feat-model-tg,feat-macro,feat-track-filter,feat-lfo-plus,feat-md-machines,feat-syntakt,feat-trig-preview,feat-trig-hold,feat-arp,feat-tempo-max,feat-trigless-dim,feat-latching-mute,feat-chord-keys,feat-sample-preview,feat-browser-scroll,feat-boot-anim,feat-multiline-browser,feat-level-pan-values,feat-usb6,feat-midi-both,feat-midi-live-both",
      "21 feature rows, by section: " + JSON.stringify(feats));
    check(w.MC_TWEAKS.features.every((f) => doc.querySelector(`#cat-${f.cat || "other"} #mod-${f.id} #feat-${f.id}`)),
      "every feature has a row in its section (cat)");
    const tagOfFeat = (f) => (f.status === "tested" ? "Tested" : "Experimental");
    const tags = w.MC_TWEAKS.features.map((f) => f.id + ":" + doc.querySelector(`label[for=feat-${f.id}] .tag`).textContent);
    check(tags.join() === w.MC_TWEAKS.features.map((f) => f.id + ":" + tagOfFeat(f)).join()
      && /Experimental/.test(tags.find((x) => x.startsWith("model-tg:"))),
      "rows tagged as tested or not (Model-TG experimental until tested here): " + tags.join());
    check(doc.getElementById("drop3-wrap").hidden, "Syntakt drop zone hidden until the Syntakt engines are ticked");
    doc.getElementById("feat-syntakt").click();
    await wait(30);
    check(!doc.getElementById("drop3-wrap").hidden && /Drop Syntakt_OS1.42.syx/.test(text(doc, "drop3"))
      && /elektron\.se\/support-downloads\/syntakt/.test(doc.getElementById("step-file").innerHTML),
      "Syntakt engines ticked -> Syntakt drop zone and download link");
    const engs = [...doc.querySelectorAll('input[name="eng-syntakt"]')];
    check(engs.map((r) => r.value + ":" + r.checked).join() === "sd:true,cp:false,toy:false,bits:false,swarm:false" && engs.every((r) => r.type === "checkbox")
      && /SDVtg — SD VINTAGE/.test(textOf(doc, "#mod-syntakt .pads")) && /CPVtg — CP VINTAGE/.test(textOf(doc, "#mod-syntakt .pads"))
      && /SYToy — SY TOY/.test(textOf(doc, "#mod-syntakt .pads")) && /SYBit — SY BITS/.test(textOf(doc, "#mod-syntakt .pads"))
      && /SYSwm — SY SWARM/.test(textOf(doc, "#mod-syntakt .pads"))
      && !/in place of SNARE/.test(text(doc, "features")) && doc.querySelectorAll('input[name="var-syntakt"]').length === 0
      && (engineCombos(w) && w.MC_TWEAKS.features.find((f) => f.engines).combos[0].tested
        ? /tested on a real Model:Cycles/ : /not tested on a Model:Cycles yet/).test(textOf(doc, "#mod-syntakt .combo")),
      "Syntakt engines: one checkbox per engine (SDVtg ticked by default, CPVtg, SYToy, SYBit, SYSwm), no SNARE replacement");
    await pickEngines(doc, ["cp"]);
    check(/not tested on a Model:Cycles yet/.test(textOf(doc, "#mod-syntakt .combo")) && /Experimental/.test(doc.querySelector("label[for=feat-syntakt] .tag").textContent),
      "CPVtg alone: a new choice, tagged Experimental");
    doc.getElementById("eng-cp").click();
    await wait(30);
    check(!doc.getElementById("feat-syntakt").checked && doc.querySelectorAll('input[name="eng-syntakt"]').length === 0
      && doc.getElementById("drop3-wrap").hidden, "last engine unticked -> the card turns off");
    // Machinedrum machines: their own drop zone for the official Machinedrum OS, never with the Syntakt engines
    check(doc.getElementById("drop4-wrap").hidden, "Machinedrum drop zone hidden until the Machinedrum machines are ticked");
    doc.getElementById("feat-md-machines").click();
    await wait(30);
    check(!doc.getElementById("drop4-wrap").hidden && /Drop Elektron_SPS1-1UW_OS1.63.syx/.test(text(doc, "drop4"))
      && /elektron\.se\/support-downloads\/machinedrum-uw/.test(doc.getElementById("step-file").innerHTML)
      && /Experimental/.test(doc.querySelector("label[for=feat-md-machines] .tag").textContent)
      && w.MCFlasherApp.chosenTweaks().map((x) => x.id).join() === "md-machines",
      "Machinedrum machines ticked -> Machinedrum drop zone and download link, tagged Experimental");
    doc.getElementById("feat-syntakt").click();
    await wait(30);
    const mdSt = w.MCFlasherApp.chosenTweaks().map((x) => x.id).join();
    if (doc.getElementById("feat-syntakt").checked) { doc.getElementById("feat-syntakt").click(); await wait(30); }
    if (doc.getElementById("feat-md-machines").checked) { doc.getElementById("feat-md-machines").click(); await wait(30); }
    check(!/md-machines.*syntakt|syntakt.*md-machines/.test(mdSt) && doc.getElementById("drop4-wrap").hidden
      && !w.MCFlasherApp.chosenTweaks().length,
      "Machinedrum machines and Syntakt engines never ticked together: " + mdSt);
    const credits = [...doc.querySelectorAll("#features .credit a")].map((a) => a.href);
    const creditOf = (id) => [...doc.querySelectorAll(`label[for=feat-${id}] .credit a`)].map((a) => a.href);
    check(credits.length === 18 && creditOf("usb6")[0] === "https://github.com/scottmetoyer/ms-multi-output"
      && /\/LICENSE-ms-multi-output\.txt$/.test(creditOf("usb6")[1])
      && creditOf("model-tg")[0] === "https://github.com/TinyGregAudio/Model-TG" && /\/LICENSE-Model-TG\.txt$/.test(creditOf("model-tg")[1])
      && creditOf("sample-preview")[0] === "https://github.com/TinyGregAudio/Model-TG" && /\/LICENSE-Model-TG\.txt$/.test(creditOf("sample-preview")[1])
      && ["latching-mute", "trig-preview", "browser-scroll"].every((id) => creditOf(id)[0] === "https://github.com/drumkilla/elektron-model-tweaks"
        && /\/LICENSE-elektron-model-tweaks\.txt$/.test(creditOf(id)[1]))
      && creditOf("macro")[0] === "https://github.com/pichenettes/eurorack" && /\/LICENSE-Braids\.txt$/.test(creditOf("macro")[1])
      && creditOf("chord-keys").join() === "https://github.com/byNicoHeuser"
      && creditOf("md-machines").join() === "https://github.com/Talachan12/Elektron-Model-Machinedrum"
      && ["midi-both", "midi-live-both"].every((id) => creditOf(id).join() === "https://github.com/AveyCole/Modded-Cycles")
      && creditOf("lfo-plus").length === 0
      && /based on a mod by DavidCaruso/.test((doc.querySelector("label[for=feat-lfo-plus] .credit") || {}).textContent || ""),
      "each row credits its author, with a link to the MIT license of the code it carries, Chord Keys by Nico Heuser, the MIDI THRU mods by AveyCole, the Machinedrum machines by Talachan12: " + JSON.stringify(credits));
    const djd = ["level-pan-values", "trigless-dim"].map((id) => doc.querySelector(`label[for=feat-${id}] .credit`));
    check(djd.every((c) => c && c.textContent === "based on a mod by djd_oz" && !c.querySelector("a")),
      "djd_oz's two mods: “based on a mod by djd_oz”, no link (no public repository)");
    const list = [...doc.querySelectorAll("#credits-list a")].map((a) => a.textContent);
    check(list.join() === "scottmetoyer/ms-multi-output,drumkilla/elektron-model-tweaks,pichenettes/eurorack,TinyGregAudio/Model-TG,mischa85/elektron-firmware-tool,dagargo/elektroid,mxldyn/octamax",
      "credits section lists the 7 upstream repositories");
    const lic = [...doc.querySelectorAll("#credits a")].map((a) => a.href).filter((h) => /LICENSE|NOTICES/.test(h));
    check(lic.join() === "https://github.com/18nelli18/Modded-Cycles/blob/main/LICENSE,https://github.com/18nelli18/Modded-Cycles/blob/main/THIRD-PARTY-NOTICES.md",
      "credits section links the project's MIT license and the third-party notices: " + JSON.stringify(lic));
    const box = (id) => doc.getElementById(id);
    // MACRO (notes/43): with Model-TG, Model-TG takes its base and MACRO the version built on it. With the Syntakt
    // engines (notes/50) both stay ticked: MACRO adds nothing itself, the engines take their version with MACRO
    const chosen = () => w.MCFlasherApp.chosenTweaks().map((x) => x.id).join();
    box("feat-macro").click(); await wait(5);
    const macroAlone = chosen();
    box("feat-model-tg").click(); await wait(5);
    const macroTg = chosen();
    const macroNote = /needs a firmware with MACRO at the same place/.test(text(doc, "features"));
    box("feat-syntakt").click(); await wait(5);
    const allThree = chosen();
    const saidTg = /SDVtg \+ MACRO with Model-TG\./.test(textOf(doc, "#mod-syntakt .combo"))
      && /With the MACRO machine: it comes last/.test(textOf(doc, "#mod-syntakt"));
    box("feat-model-tg").click(); await wait(5);
    const withEng = chosen();
    const bothOn = box("feat-macro").checked && box("feat-syntakt").checked && /SDVtg \+ MACRO\./.test(textOf(doc, "#mod-syntakt .combo"))
      && /With Real Syntakt engines: (checked in the emulator|tried on the machine)/.test(textOf(doc, "#det-macro"));
    box("feat-syntakt").click(); await wait(5);
    box("feat-macro").click(); await wait(5);
    check(macroAlone === "macro" && macroTg === "model-tg-st,macro-tg" && macroNote && allThree === "model-tg-st,syntakt-tg-sd-macro"
      && saidTg && withEng === "syntakt-sd-macro" && bothOn && !chosen().length && doc.querySelector('#features a[href$="#macro"]'),
      `MACRO: alone ${macroAlone}, with Model-TG ${macroTg}, its note shown; with the Syntakt engines ${withEng}, and with Model-TG too ${allThree}`);
    // Model-TG holds drumkilla's tweaks: ticked, it shows them ticked and locked, "(included with Model-TG)", and
    // builds without them; unticked, they are free again. With the Syntakt engines it makes the combined version
    // (notes/31): its base, then the engines' tweak built on top of it
    const drum = ["feat-latching-mute", "feat-trig-preview", "feat-browser-scroll"];
    box("feat-latching-mute").click(); await wait(5);
    box("feat-syntakt").click(); await wait(5);
    box("feat-model-tg").click(); await wait(5);
    const locked = drum.every((id) => box(id).checked && box(id).disabled
      && /\(included with Model-TG\)/.test(doc.querySelector(`label[for=${id}] .ttl`).textContent)) && box("feat-syntakt").checked;
    const noteOn = /set to CYC/.test(textOf(doc, "#mod-model-tg .say")) && /its Sampler is the 7th machine/.test(textOf(doc, "#mod-syntakt .combo"));
    const both = w.MCFlasherApp.chosenTweaks().map((x) => x.id).join();
    box("feat-trig-preview").click(); await wait(5);                 // locked: nothing changes
    const still = box("feat-model-tg").checked && box("feat-trig-preview").checked
      && w.MCFlasherApp.chosenTweaks().map((x) => x.id).join() === both;
    box("feat-model-tg").click(); await wait(5);
    const freed = drum.every((id) => !box(id).checked && !box(id).disabled) && !/included with/.test(text(doc, "features"));
    box("feat-trig-preview").click(); await wait(5);
    check(locked && noteOn && both === "model-tg-st,syntakt-tg-sd" && still && freed
      && box("feat-trig-preview").checked && w.MCFlasherApp.chosenTweaks().map((x) => x.id).join() === "trig-preview,syntakt-sd",
      "Model-TG shows drumkilla's tweaks ticked, locked and included (not built), frees them when unticked, shows its install note; with the Syntakt engines: " + both);
    box("feat-model-tg").click(); await wait(5);                     // ticked over trig-preview: it becomes included
    const over = box("feat-trig-preview").checked && box("feat-trig-preview").disabled
      && w.MCFlasherApp.chosenTweaks().map((x) => x.id).join() === "model-tg-st,syntakt-tg-sd";
    box("feat-model-tg").click(); await wait(5);
    check(over && !box("feat-trig-preview").checked && !box("feat-trig-preview").disabled,
      "Model-TG ticked over trig-preview: shown included, built without it; unticked: all free and unticked");
    // Sample preview needs Model-TG (card field "requires"): ticking it ticks Model-TG too, as if the user had (its
    // exclusions apply); unticking Model-TG unticks it; with the Syntakt engines (still ticked here, SDVtg) both
    // take their combined version, and the card keeps its own badge (not the combined version's tests)
    const ids1 = () => w.MCFlasherApp.chosenTweaks().map((x) => x.id).join();
    const spCard = () => doc.querySelector("label[for=feat-sample-preview]");
    const spTag = tagOfFeat(w.MC_TWEAKS.features.find((f) => f.id === "sample-preview"));
    box("feat-sample-preview").click(); await wait(5);
    const reqSt = box("feat-sample-preview").checked && box("feat-model-tg").checked && box("feat-syntakt").checked
      && ids1() === "model-tg-st,sample-preview-st,syntakt-tg-sd" && spCard().querySelector(".tag").textContent === spTag;
    const five = ["sd", "cp", "toy", "bits", "swarm"];    // Model-TG + the 5 engines: the combined version's badge
    await pickEngines(doc, five);
    const tg5 = !!w.MC_TWEAKS.features.find((f) => f.id === "syntakt").combos.find((c) => c.engines.join() === five.join()).tg_tested;
    const reqSt5 = ids1() === "model-tg-st,sample-preview-st,syntakt-tg-sd-cp-toy-bits-swarm"
      && spCard().querySelector(".tag").textContent === spTag
      && doc.querySelector("label[for=feat-model-tg] .tag").textContent === (tg5 ? "Tested" : "Experimental");
    await pickEngines(doc, ["sd"]);
    box("feat-syntakt").click(); await wait(5);
    const reqPlain = ids1() === "model-tg,sample-preview";
    box("feat-sample-preview").click(); await wait(5);
    const keepTg = box("feat-model-tg").checked && !box("feat-sample-preview").checked && ids1() === "model-tg";
    box("feat-model-tg").click(); await wait(5);
    box("feat-latching-mute").click(); await wait(5);
    box("feat-sample-preview").click(); await wait(5);
    const reqOn = box("feat-model-tg").checked && box("feat-sample-preview").checked
      && box("feat-latching-mute").checked && box("feat-latching-mute").disabled && ids1() === "model-tg,sample-preview"
      && /^with Model-TG$/.test(spCard().querySelector(".need").textContent)
      && /Model-TG only: ticking this one ticks it too/.test(textOf(doc, "#det-sample-preview"))
      && !!doc.querySelector('#mod-sample-preview a[href$="#sample-preview"]');
    box("feat-model-tg").click(); await wait(5);
    const reqOff = !box("feat-model-tg").checked && !box("feat-sample-preview").checked
      && !box("feat-latching-mute").checked && !box("feat-latching-mute").disabled && ids1() === "";
    box("feat-macro").click(); await wait(5);                        // with MACRO: Model-TG's base, like the engines
    box("feat-sample-preview").click(); await wait(5);
    const reqMacro = box("feat-model-tg").checked && box("feat-macro").checked
      && ids1() === "model-tg-st,sample-preview-st,macro-tg" && spCard().querySelector(".tag").textContent === spTag;
    box("feat-model-tg").click(); await wait(5);
    const macroLeft = box("feat-macro").checked && !box("feat-sample-preview").checked && ids1() === "macro";
    box("feat-macro").click(); await wait(5);
    check(reqSt && reqSt5 && reqPlain && keepTg && reqOn && reqOff && reqMacro && macroLeft && ids1() === "",
      "sample preview: says « with Model-TG » (Details: only with it), ticking it ticks Model-TG (latching mute then included), unticking Model-TG "
      + "unticks it, unticking it keeps Model-TG; with the Syntakt engines: model-tg-st,sample-preview-st,syntakt-tg-…; with MACRO: "
      + "model-tg-st,sample-preview-st,macro-tg; "
      + `its own badge (${spTag}, Model-TG + the 5 engines: ${tg5 ? "Tested" : "Experimental"}); guide link`);
    // the combined version's badges follow its tests on the hardware (gen_syntakt_engines.HW_TESTED_TG, the
    // combos' tg_tested in tweaks.js): Model-TG + the 5 engines, then Model-TG + SDVtg alone
    doc.getElementById("feat-model-tg").click(); await wait(5);
    const tgCombos = w.MC_TWEAKS.features.find((f) => f.id === "syntakt").combos;
    const tgTested = (codes) => !!tgCombos.find((c) => c.engines.join() === codes.join()).tg_tested;
    const tagOf = (id) => doc.querySelector(`label[for=${id}] .tag`).textContent;
    const badges = async (codes) => {
      await pickEngines(doc, codes);
      const want = tgTested(codes) ? "Tested" : "Experimental";
      const note = tgTested(codes) ? /tested on a real Model:Cycles/ : /not tested on a Model:Cycles yet/;
      return note.test(textOf(doc, "#mod-syntakt .combo")) && tagOf("feat-syntakt") === want && tagOf("feat-model-tg") === want;
    };
    const all5 = ["sd", "cp", "toy", "bits", "swarm"];
    const badgesOk = await badges(all5) && await badges(["sd"]);
    const word = (codes) => (tgTested(codes) ? "tested" : "experimental");
    check(badgesOk, `Model-TG + the 5 engines: ${word(all5)} (both cards); Model-TG + SDVtg alone: ${word(["sd"])}`);
    doc.getElementById("feat-model-tg").click(); await wait(5);
    doc.getElementById("feat-syntakt").click(); await wait(5);
    doc.getElementById("feat-usb6").click();
    await wait(30);
    check(doc.querySelectorAll('input[name="var-usb6"]').length === 0, "6 channels: a single variant, no sub-choice");
    check(!!doc.getElementById("tab-samples") && doc.getElementById("panel-samples").hidden && doc.getElementById("drop2-wrap").hidden,
      "Samples OS tab present, its panel and second drop zone hidden in Mods");
    check(/Load your official OS file/.test(text(doc, "missing")), "flash button says what is missing: " + text(doc, "missing"));
    check(doc.getElementById("flash").disabled, "flash button disabled without a file");

    // language switch
    doc.querySelector('.lang button[data-lang="fr"]').click();
    await wait(20);
    check(/Que voulez-vous installer/.test(text(doc, "h1s")) && doc.documentElement.lang === "fr", "FR switch translates the page");
    check(/Audio USB 6 canaux/.test(text(doc, "features")) && /Mode mute verrouillé/.test(text(doc, "features"))
      && /par drumkilla/.test(text(doc, "features")) && /Vrais moteurs du Syntakt/.test(text(doc, "features"))
      && /Testé/.test(text(doc, "features")), "FR switch translates the feature cards and credits");
    check(/Crédits/.test(text(doc, "credits")) && /boîte à outils/.test(text(doc, "credits")) && /publié sous licence MIT/.test(text(doc, "credits")),
      "FR switch translates the credits section");
    check(/Tempo jusqu'à 546 BPM/.test(text(doc, "features")) && doc.querySelector('label[for=feat-tempo-max] a.feat-guide, #features a[href$="#tempo"]'),
      "FR: tempo card translated, with its guide link");
    check(/Animation de démarrage modded-cycles/.test(text(doc, "features")) && doc.querySelector('#features a[href$="#boot-anim"]'),
      "FR: startup animation card translated, with its guide link");
    check(/Volume et pan en chiffres/.test(text(doc, "features")) && doc.querySelector('#features a[href$="#level-pan"]')
      && /Trigless trigs atténués/.test(text(doc, "features")) && doc.querySelector('#features a[href$="#trigless"]')
      && /d'après un mod de djd_oz/.test(text(doc, "features")),
      "FR: djd_oz's two cards translated, with their guide links and credit");
    check(/Navigateur sur plusieurs lignes/.test(text(doc, "features")) && doc.querySelector('#features a[href$="#multiline"]'),
      "FR: multi-line browser card translated, with its guide link");
    check(/MIDI OUT pendant THRU/.test(text(doc, "features")) && /relaie le MIDI reçu/.test(text(doc, "features"))
      && /par AveyCole/.test(textOf(doc, "#mod-midi-both")) && doc.querySelector('#features a[href$="#midi-both"]')
      && /Ne va pas avec/.test(textOf(doc, "#det-midi-both")) && /Basculer MIDI OUT \+ THRU en direct/.test(textOf(doc, "#det-midi-both")),
      "FR: MIDI OUT during THRU row translated, credited to AveyCole, with its guide link (Détails : ne va pas avec la bascule)");
    check(/Basculer MIDI OUT \+ THRU en direct/.test(text(doc, "features")) && /FUNC \+ appui sur LEVEL\/DATA/.test(text(doc, "features"))
      && /par AveyCole/.test(textOf(doc, "#mod-midi-live-both")) && doc.querySelector('#features a[href$="#midi-live-both"]'),
      "FR: live MIDI toggle row translated, credited to AveyCole, with its guide link");
    check(/Écoute des samples \(Model-TG\)/.test(text(doc, "features"))
      && /^avec Model-TG$/.test(doc.querySelector("label[for=feat-sample-preview] .need").textContent)
      && /Model-TG seulement : cocher celui-ci le coche aussi/.test(textOf(doc, "#det-sample-preview"))
      && doc.querySelector('#mod-sample-preview a[href$="#sample-preview"]'),
      "FR: sample preview row translated, says « avec Model-TG » (Détails : seulement avec lui), with its guide link");
    check(/Machine MACRO/.test(text(doc, "features")) && /tirés du code libre de Braids/.test(text(doc, "features")) && /d'après eurorack d'Émilie Gillet/.test(text(doc, "features"))
      && doc.querySelector('#features a[href$="#macro"]'), "FR: MACRO card translated, with its credit and guide link");
    check(/Chord Keys/.test(text(doc, "features"))
      && doc.querySelector('#features a[href$="#chord-keys"]'),
      "FR: chord keyboard translated, with its guide link");
    check(/Filtre par piste \(LP \/ OFF \/ HP\)/.test(text(doc, "features")) && doc.querySelector('#features a[href$="#track-filter"]'),
      "FR: per-track filter card translated, with its guide link");
    doc.getElementById("feat-model-tg").click(); await wait(5);
    doc.getElementById("feat-track-filter").click(); await wait(5);
    const tfOn = doc.getElementById("feat-track-filter").checked, tgOff = !doc.getElementById("feat-model-tg").checked;
    doc.getElementById("feat-model-tg").click(); await wait(5);
    check(tfOn && tgOff && doc.getElementById("feat-model-tg").checked && !doc.getElementById("feat-track-filter").checked,
      "per-track filter and Model-TG can't be ticked together: ticking one unticks the other");
    doc.getElementById("feat-model-tg").click(); await wait(5);
    doc.getElementById("feat-chord-keys").click(); await wait(5);
    check(doc.getElementById("feat-chord-keys").checked && !doc.getElementById("feat-model-tg").checked,
      "Chord Keys selection excludes Model-TG");
    doc.getElementById("feat-model-tg").click(); await wait(5);
    check(!doc.getElementById("feat-chord-keys").checked,
      "Model-TG selection excludes Chord Keys in the other direction");
    check(/\(inclus avec Model-TG\)/.test(doc.querySelector("label[for=feat-browser-scroll] .ttl").textContent),
      "FR: the tweaks Model-TG holds say « (inclus avec Model-TG) »");
    doc.getElementById("feat-model-tg").click(); await wait(5);
    doc.querySelector('.lang button[data-lang="en"]').click();
    await wait(20);

    // Connection: USB only, fast method by default, classic as the fallback
    check(doc.querySelectorAll('input[name="method"]').length === 0 && !doc.getElementById("howto-midi")
      && !/MIDI IN|READY TO RECEIVE|TRIG 4/.test(text(doc, "step-connect")), "no MIDI IN route in step 3");
    check(doc.getElementById("m-fast").getAttribute("aria-checked") === "true" && !doc.getElementById("howto-fast").hidden
      && doc.getElementById("howto-usb").hidden && /Close Elektron Transfer/.test(text(doc, "howto-fast"))
      && !/CONFIG › UPGRADE/.test(text(doc, "howto-fast")) && /about 30 seconds/.test(text(doc, "method-note")),
      "fast method by default: its steps (close Transfer, no menu to open)");
    doc.getElementById("allow").click();
    await wait(150);
    const sel = doc.getElementById("port");
    check(!sel.hidden && sel.value === "dev", "Allow MIDI -> Model:Cycles port preselected (" + sel.value + ")");
    check(/Model:Cycles found: OS 1\.13/.test(text(doc, "midi-status")) && doc.getElementById("step-connect").classList.contains("done"),
      "fast: the machine is asked who it is: " + text(doc, "midi-status").slice(0, 50));
    doc.getElementById("m-slow").click();
    await wait(20);
    check(/CONFIG › UPGRADE/.test(text(doc, "howto-usb")) && !doc.getElementById("howto-usb").hidden && doc.getElementById("howto-fast").hidden
      && /USB port is selected/.test(text(doc, "midi-status")) && /5 to 10 minutes/.test(text(doc, "method-note")),
      "classic method: CONFIG › UPGRADE steps, status: " + text(doc, "midi-status").slice(0, 50));
    sel.value = "iface";
    sel.dispatchEvent(new w.Event("change"));
    await wait(20);
    check(/pick the port named/i.test(text(doc, "midi-status")), "another port -> warning");
    doc.getElementById("m-fast").click();
    await wait(20);
    check(/pick the port named/i.test(text(doc, "midi-status")) && w.MCFlasherApp.state.dev.state === "noinput", "fast, another port (output only) -> warning");
    doc.querySelector('.lang button[data-lang="fr"]').click();
    await wait(20);
    check(/Rapide \(USB\)/.test(text(doc, "m-fast")) && /Fermez Elektron Transfer/.test(text(doc, "howto-fast")), "FR: method and steps translated");
    doc.querySelector('.lang button[data-lang="en"]').click();
    await wait(20);
  }

  // 1b. The mod picker: sections, build order, Details, folding, the selection bar, conflicts with Undo,
  // "Use this choice", focus, search, French
  if (MAIN) {
    const { w, doc, errors } = await load();
    const app = w.MCFlasherApp;
    const feats = w.MC_TWEAKS.features;
    const box = (id) => doc.getElementById(id);
    const click = async (el) => { el.click(); await wait(5); };
    const ids = () => app.chosenTweaks().map((x) => x.id).join();
    const clearAll = async () => { const b = doc.querySelector("#mod-sel [data-clear]"); if (b) await click(b); };
    const sections = [...doc.querySelectorAll("#features section.grp")].map((g) => g.id.slice(4));
    check(sections.join() === app.CATS.filter((c) => feats.some((f) => (f.cat || "other") === c)).join() && !box("cat-other"),
      "sections in CATS order, no « Other mods » while every mod has a cat: " + sections.join());
    check([...doc.querySelectorAll("#cats a[data-cat]")].map((a) => a.dataset.cat).join() === sections.join()
      && doc.querySelector('#cats a[data-cat="seq"]').getAttribute("href") === "#cat-seq", "one chip per section, linking to it");
    // the build keeps FEATURES order whatever the display order
    await click(box("feat-arp"));
    await click(box("feat-usb6"));
    check(ids() === "6ch-usbup,arp", "build order unchanged (USB ticked after the arpeggiator): " + ids());
    check(/2 mods/.test(text(doc, "mod-live")) && doc.querySelector('#cats a[data-cat="seq"] .led.on')
      && !doc.querySelector('#cats a[data-cat="screen"] .led.on'), "screen readers hear the count; the LED of a section with a ticked mod lights");
    await clearAll();
    // a mod without a cat lands in « Other mods », at the end
    const boot = feats.find((f) => f.id === "boot-anim"), bootCat = boot.cat;
    delete boot.cat;
    app.applyLang("en");
    check(!!doc.querySelector("#cat-other #feat-boot-anim") && /Other mods/.test(textOf(doc, "#cat-other .grp-h"))
      && [...doc.querySelectorAll("#features section.grp")].pop().id === "cat-other", "a mod without cat goes to « Other mods », last");
    boot.cat = bootCat;
    app.applyLang("en");
    // Details: opens and closes, doesn't tick, holds the guide link
    await click(box("more-arp"));
    const opened = !box("det-arp").hidden && box("more-arp").getAttribute("aria-expanded") === "true" && !box("feat-arp").checked
      && !!doc.querySelector('#det-arp a[href$="#arp"]') && /Status/.test(text(doc, "det-arp"));
    await click(box("more-arp"));
    check(opened && box("det-arp").hidden && box("more-arp").getAttribute("aria-expanded") === "false",
      "Details opens the drawer (description, status, guide link) without ticking, and closes it");
    // folding a section; a folded section still names its ticked mods; its chip unfolds it
    await click(box("feat-arp"));
    await click(box("grp-h-seq"));
    const folded = box("grp-seq").hidden && box("grp-h-seq").getAttribute("aria-expanded") === "false"
      && /Arpeggiator/.test(textOf(doc, "#cat-seq .grp-sel"));
    await click(doc.querySelector('#cats a[data-cat="seq"]'));
    check(folded && !box("grp-seq").hidden, "a folded section names its ticked mods, its chip unfolds it");
    await clearAll();
    // the selection bar
    check(/No mod ticked yet/.test(text(doc, "mod-sel")) && !doc.querySelector("#mod-sel .sel-next"), "selection bar, empty");
    await click(box("feat-usb6"));
    await click(box("feat-model-tg"));
    const counts = textOf(doc, "#mod-sel .sel-c");
    check(/2 mods \+ 3 included/.test(counts) && doc.querySelectorAll("#mod-sel .chip").length === 2
      && doc.querySelector("#mod-sel a.sel-next").getAttribute("href") === "#step-file", "selection bar: " + counts);
    await click(doc.querySelector('#mod-sel [data-off="model-tg"]'));
    check(ids() === "6ch-usbup" && !box("feat-model-tg").checked && doc.activeElement && doc.activeElement.dataset.off === "usb6",
      "× on a chip unticks the mod, the focus goes to the next ×");
    await clearAll();
    check(ids() === "" && /No mod ticked yet/.test(text(doc, "mod-sel")), "« Untick all » empties the selection");
    // a conflict injected between two mods that do go together (no two mods clash today), said before ticking, then
    // Undo
    const tempo = feats.find((f) => f.id === "tempo-max");
    tempo.excludes = ["arp"];
    await click(box("feat-arp"));
    const said = /Doesn't go with the mod “Arpeggiator”/.test(textOf(doc, "#mod-tempo-max .say.clash"))
      && /Doesn't go with/.test(textOf(doc, "#det-tempo-max")) && !doc.querySelector("#mod-arp .say.clash");
    await click(box("feat-tempo-max"));
    const swapped = ids() === "tempo-max" && /The mod “Arpeggiator” was unticked/.test(textOf(doc, "#mod-tempo-max .say.swap"))
      && /The mod “Arpeggiator” was unticked/.test(textOf(doc, "#mod-sel .sel-msg"));
    await click(doc.querySelector("#mod-tempo-max [data-undo]"));
    check(said && swapped && ids() === "arp" && !box("feat-tempo-max").checked && !doc.querySelector(".say.swap")
      && doc.activeElement && doc.activeElement.id === "feat-tempo-max",
      "conflict: said on the row before ticking; ticking unticks the other one, with Undo");
    delete tempo.excludes;
    await clearAll();
    // "Use this choice": the engines already tried on the machine (with Model-TG: the combined version's own tests)
    const syn = feats.find((f) => f.engines);
    const triedTg = syn.combos.filter((c) => c.tg_tested);
    await click(box("feat-model-tg"));
    await pickEngines(doc, ["sd"]);
    const take = doc.querySelector("#mod-syntakt [data-take]");
    if (triedTg.length && !triedTg.some((c) => c.engines.join() === "sd")) {
      const codes = take && take.dataset.codes;
      if (take) await click(take);
      const now = [...doc.querySelectorAll('input[name="eng-syntakt"]')].filter((x) => x.checked).map((x) => x.value).join();
      check(!!take && now === codes && doc.querySelector("label[for=feat-syntakt] .tag").textContent === "Tested"
        && doc.querySelector("label[for=feat-model-tg] .tag").textContent === "Tested",
        "« Use this choice » ticks the engines tried on the machine with Model-TG (" + codes + "): both rows Tested");
    } else console.log("  skip « Use this choice »: Model-TG + SDVtg is tried on the machine, or nothing is");
    // the selection bar's "+ Syntakt OS file" line survives a language switch made in another tab
    const need = () => !!doc.querySelector("#mod-sel .sel-need");
    const needHere = box("feat-syntakt").checked && need();
    app.setMode("samples"); app.applyLang("fr"); app.setMode("mods"); await wait(5);
    check(needHere && need() && /Syntakt/.test(textOf(doc, "#mod-sel .sel-need")),
      "selection bar keeps « + Syntakt OS file » after a language switch in the Samples OS tab");
    app.applyLang("en");
    await clearAll();
    // focus stays on the checkbox just ticked, although the rows are rebuilt
    const arp = box("feat-arp");
    arp.focus();
    await click(arp);
    check(box("feat-arp") !== arp && doc.activeElement && doc.activeElement.id === "feat-arp", "focus kept on the ticked box after the rebuild");
    await clearAll();
    // search: hidden under 20 mods; from 20, by words in both languages, accents ignored
    check(feats.length >= 20 && !box("mod-find").hidden, `search field with ${feats.length} mods`);
    const q = box("mod-q");
    q.value = "ÉCOUTE";
    q.dispatchEvent(new w.Event("input"));
    await wait(5);
    const found = !box("mod-find").hidden && !box("mod-trig-preview").hidden && !box("mod-sample-preview").hidden
      && box("mod-usb6").hidden && box("cat-io").hidden && new RegExp(`2 of ${feats.length} mods`).test(text(doc, "mod-found"));
    box("mod-q").dispatchEvent(new w.KeyboardEvent("keydown", { key: "Escape" }));
    await wait(5);
    check(found && !box("mod-usb6").hidden && box("mod-found").hidden && box("mod-q").value === "",
      "search from 20 mods: « ÉCOUTE » finds Trig preview and Sample preview (French names, any case or accent); Esc shows all again");
    const n = feats.length, out = [], needed = new Set(feats.map((f) => f.requires).filter(Boolean));
    for (let i = n - 1; i >= 0 && feats.length > 19; i--)
      if (!feats[i].engines && !needed.has(feats[i].id)) out.unshift([i, feats.splice(i, 1)[0]]);
    app.applyLang("en");
    check(feats.length === 19 && box("mod-find").hidden && out.every(([, f]) => !box("mod-" + f.id)),
      `no search field with ${feats.length} mods (hidden under 20)`);
    for (const [i, f] of out) feats.splice(i, 0, f);
    app.applyLang("en");
    check(!box("mod-find").hidden && feats.length === n && out.every(([, f]) => box("mod-" + f.id)), "back to " + feats.length + " mods");
    // French
    app.applyLang("fr");
    await click(box("feat-model-tg"));
    check(/Séquenceur/.test(textOf(doc, "#cat-seq .grp-h")) && /Votre sélection/.test(text(doc, "mod-sel"))
      && /Détails/.test(textOf(doc, "#more-arp")) && /1 mod \+ 3 inclus/.test(textOf(doc, "#mod-sel .sel-c"))
      && ["latching-mute", "trig-preview", "browser-scroll"].every((id) => /\(inclus avec Model-TG\)/.test(textOf(doc, `#mod-${id} .ttl`)))
      && /Rubriques/.test(box("cats").getAttribute("aria-label")),
      "FR: sections, selection bar, Details, « inclus avec Model-TG »");
    await clearAll();
    app.applyLang("en");
    check(errors.length === 0, "no JS error in the mod picker " + (errors.length ? JSON.stringify(errors) : ""));
  }

  // 1c. Fast method: a machine that doesn't answer (CONFIG > UPGRADE open, Transfer running), no MIDI input
  if (MAIN) {
    const { doc, dev } = await load({ device: { silent: true } });
    doc.getElementById("allow").click();
    await wait(1300);
    check(/doesn't answer/.test(text(doc, "midi-status")) && dev.pings === 1, "silent machine -> 'doesn't answer' after the 1 s handshake");
    dev.silent = false;
    doc.getElementById("refresh").click();
    await wait(150);
    check(/Model:Cycles found/.test(text(doc, "midi-status")) && dev.pings === 2, "Refresh asks again -> found");
  }
  if (MAIN) {
    const { doc } = await load({ busy: true });
    doc.getElementById("allow").click();
    await wait(100);
    check(/in use by another program: close Elektron Transfer/.test(text(doc, "midi-status")), "port held by another program -> says so");
  }
  if (MAIN) {
    const { doc } = await load({ inputs: false });
    doc.getElementById("allow").click();
    await wait(100);
    check(/no MIDI input from the Model:Cycles/.test(text(doc, "midi-status")), "no MIDI input -> says the fast method needs both directions");
  }

  // 1b. A Model:Cycles running the Samples OS shows up as "Model:Samples": it refuses a Model:Cycles firmware
  if (MAIN) {
    const { doc } = await load({ devName: "Elektron Model:Samples", device: { id: 25, name: "Model Samples" } });
    doc.getElementById("allow").click();
    await wait(150);
    check(doc.getElementById("port").value === "dev" && /Model:Samples found/.test(text(doc, "midi-status")),
      "fast: Model:Samples port -> identified: " + text(doc, "midi-status").slice(0, 60));
    doc.getElementById("m-slow").click();
    await wait(20);
    check(/refuses a Model:Cycles firmware/.test(text(doc, "midi-status")), "classic: Model:Samples port -> warning about the way back");
  }

  // 2. No Web MIDI (Firefox / Safari) -> clear banner
  if (MAIN) {
    const { doc } = await load({ midi: false });
    check(!doc.getElementById("compat").hidden && /Chrome, Edge or Opera/.test(text(doc, "compat")), "no Web MIDI -> banner");
    check(doc.getElementById("allow").disabled, "no Web MIDI -> Allow button disabled");
  }

  // 3. Insecure context (file://) -> clear banner
  if (MAIN) {
    const { doc } = await load({ secure: false });
    check(/secure page/i.test(text(doc, "compat")), "file:// -> banner: " + text(doc, "compat").slice(0, 40));
  }

  // 4. French browser -> French page
  if (MAIN) {
    const { doc } = await load({ lang: "fr-FR" });
    check(doc.documentElement.lang === "fr" && /Flasher Model:Cycles/.test(text(doc, "step-flash") + doc.title), "fr-FR browser -> French page");
  }

  // 5. Build from a synthetic OS, then flash, then stop
  if (SYNTH && MAIN) {
    const env5 = await load();
    const { w, doc, errors, sent } = env5;
    const raw = new Uint8Array(fs.readFileSync(path.join(SYNTH, "synth.syx")));
    const meta = JSON.parse(fs.readFileSync(path.join(SYNTH, "meta.json")));
    const app = w.MCFlasherApp;
    // the synthetic OS stands in for the official one
    w.MC_TWEAKS.device.section_sha256 = meta.section_sha256;
    w.MC_TWEAKS.device.stock_syx_sha256 = w.MCBuilder.hex(w.MCBuilder.sha256(raw));
    for (const k of Object.keys(app.REF_MAINOS)) delete app.REF_MAINOS[k];
    app.loadOs(raw, "synth.syx");
    await wait(20);
    check(/Official Model:Cycles OS 1.13 recognised/.test(text(doc, "file-status")), "OS file recognised as official");
    check(/Select a mod/.test(text(doc, "missing")), "no mod selected -> asks for one");
    doc.getElementById("feat-usb6").click();
    await settle(w);
    check(app.state.fw && app.state.fw.kind === "built" && /Firmware ready/.test(text(doc, "file-status")), "mod checked -> firmware built automatically");
    app.setMode("restore");
    await settle(w);
    check(app.state.fw && app.state.fw.kind === "stock", "Official firmware tab -> sends the OS unchanged");
    app.setMode("mods");
    await settle(w);
    check(app.state.fw && app.state.fw.kind === "built", "back to Mods -> built firmware again (cache)");
    doc.getElementById("feat-syntakt").click();
    await settle(w);
    check(!app.state.fw && app.state.fwError === "needs_syntakt" && /read from the official Syntakt OS/.test(text(doc, "file-status"))
      && /Load the official Syntakt OS file/.test(text(doc, "missing")), "Syntakt engines without the Syntakt file -> asks for it");
    app.loadSyntakt(raw, "Syntakt_OS1.42.syx");
    await settle(w);
    check(!app.state.syntakt && /not the official Syntakt OS 1.42/.test(text(doc, "file3-status")), "a wrong file in the Syntakt zone is refused");
    doc.getElementById("feat-syntakt").click();
    await settle(w);
    check(app.state.fw && app.state.fw.kind === "built" && doc.getElementById("drop3-wrap").hidden, "Syntakt engines unticked -> back to the 6-channel build");

    doc.getElementById("allow").click();
    await wait(150);
    check(/Tick the box/.test(text(doc, "missing")), "asks for the confirmation box");
    doc.getElementById("ack").click();
    await wait(20);
    check(!doc.getElementById("flash").disabled, "flash button enabled when everything is ready");
    const fastMin = Math.max(1, Math.round(w.MCFlasher.fastSeconds(app.state.fw.raw) / 60));   // 2.5 MB synthetic file: 2 min
    check(text(doc, "summary").endsWith(`via Elektron Model:Cycles · about ${fastMin} min`) && fastMin <= 2 && /confirm on its screen/.test(text(doc, "missing")),
      "fast summary: " + text(doc, "summary"));
    const dl = doc.getElementById("download");
    check(!doc.getElementById("alt").hidden && dl.getAttribute("download") === app.state.fw.name && /Elektron Transfer/.test(text(doc, "alt")),
      "step 4 offers the .syx for Elektron Transfer: " + dl.getAttribute("download"));

    // fast: stop during the transfer (real 50 ms pause between blocks)
    const { dev } = env5;
    doc.getElementById("flash").click();
    await wait(400);
    check(!doc.getElementById("stop").hidden && /Flashing/.test(text(doc, "flash")) && dev.starts === 1 && dev.blocks > 1
      && doc.getElementById("m-slow").disabled, `fast transfer running: ${dev.blocks} blocks acknowledged, method locked`);
    doc.getElementById("stop").click();
    await untilSent(w);
    check(app.state.finished === "stopped" && /Stopped before the end/.test(text(doc, "result")) && dev.next < dev.size,
      "fast: Stop -> clear message, the machine didn't get the whole file");

    // fast: full transfer, byte for byte, then the machine restarts
    noRest(w);
    const fw5 = app.state.fw.raw;
    doc.getElementById("flash").click();
    await untilSent(w);
    check(app.state.finished === "ok" && same(dev.received, fw5) && dev.bad.length === 0 && dev.starts === 2
      && dev.blocks === Math.ceil(fw5.length / 0x800),
      `fast: the machine received the whole .syx, byte for byte, CRC checked (${dev.blocks} blocks) ` + dev.bad.slice(0, 2).join("; "));
    check(/Firmware sent/.test(text(doc, "result")) && /confirm the update on the Model:Cycles screen/.test(text(doc, "after"))
      && /6 input channels/.test(text(doc, "result")), "fast: success -> confirm on the machine, 6-channel hint");
    const out5 = env5.devOut(), in5 = env5.devIn();
    out5.state = in5.state = "disconnected";
    env5.access().onstatechange({ port: out5 });
    await wait(20);
    check(/writing the firmware and restarting/.test(text(doc, "after")), "machine gone -> 'writing and restarting'");
    out5.state = in5.state = "connected";
    dev.version = "1.13B";
    env5.access().onstatechange({ port: out5 });
    await wait(2800);
    check(/is back: Model:Cycles OS 1\.13B/.test(text(doc, "after")), "machine back -> asked again: " + text(doc, "after"));

    // fast: refusals
    dev.startStatus = 1;
    doc.getElementById("flash").click();
    await untilSent(w);
    check(app.state.finished === "error" && /refused the update \(“No space”\)/.test(text(doc, "result")), "start refused -> " + text(doc, "result").slice(0, 60));
    dev.startStatus = 0; dev.writeError = 3;
    doc.getElementById("flash").click();
    await untilSent(w);
    check(app.state.finished === "error" && /error while receiving/.test(text(doc, "result")) && dev.blocks === 4, "block refused -> stops there");
    dev.writeError = -1; dev.id = 25;
    doc.getElementById("refresh").click();
    await wait(150);
    check(doc.getElementById("flash").disabled && /can't take this firmware/.test(text(doc, "missing"))
      && /answers as a Model:Samples/.test(text(doc, "midi-status")), "machine answering as a Model:Samples (Model-TG on SMP) -> nothing sent");
    dev.id = 27;
    doc.getElementById("refresh").click();
    await wait(150);
    check(!doc.getElementById("flash").disabled, "back to a Model:Cycles -> ready");

    // classic method
    doc.getElementById("m-slow").click();
    await wait(20);
    check(/via Elektron Model:Cycles · about \d+ min/.test(text(doc, "summary")) && /Open CONFIG › UPGRADE/.test(text(doc, "missing")),
      "classic summary: " + text(doc, "summary"));

    // stop during a paced transfer
    doc.getElementById("flash").click();
    await wait(400);
    check(!doc.getElementById("stop").hidden && /Flashing/.test(text(doc, "flash")), "during transfer: Stop visible, button busy");
    doc.getElementById("stop").click();
    for (let i = 0; i < 40 && app.state.sending; i++) await wait(50);
    check(app.state.finished === "stopped" && /Stopped/.test(text(doc, "result")), "Stop -> clear 'stopped' message");

    // full transfer at pace 0
    const n0 = sent.length;
    doc.getElementById("pace").value = "0";
    doc.getElementById("pace").dispatchEvent(new w.Event("input"));
    doc.getElementById("flash").click();
    for (let i = 0; i < 200 && app.state.sending; i++) await wait(50);
    const total = w.MCFlasher.splitMessages(app.state.fw.raw).length;
    check(sent.length - n0 === total, `every packet sent (${sent.length - n0}/${total})`);
    check(app.state.finished === "ok" && /Transfer complete/.test(text(doc, "result")) && /UPDATING FLASH/.test(text(doc, "result")),
      "success message shown");
    check(/6 input channels/.test(text(doc, "result")), "6-channel hint after success");
    check(errors.length === 0, "no JS error during the flow " + (errors.length ? JSON.stringify(errors) : ""));
  }

  // 5b. The page's own rules against the sample (notes/49): each card alone and every pair of cards the page lets you
  // tick together, whatever it does with them (a card held by another, a swap), is a combination of REF_MAINOS.
  // No OS needed: the build key is chosenTweaks().
  if (MAIN) {
    const { w, doc, errors } = await load();
    const app = w.MCFlasherApp, feats = w.MC_TWEAKS.features;
    const keyNow = () => app.chosenTweaks().map((x) => x.id).join("+");
    const choices = (f) => (f.engines ? f.combos.map((c) => ({ engines: c.engines })) : f.variants.map((v) => ({ variant: v.id })));
    const clear = async () => {
      for (let round = 0; round < 3; round++)
        for (const f of feats) {
          const cb = doc.getElementById("feat-" + f.id);
          if (cb.checked && !cb.disabled) { cb.click(); await wait(5); }
        }
    };
    const pick = async (f, o) => {                   // false if the page holds the card (included by another one)
      if (o.engines) { await pickEngines(doc, o.engines); return true; }
      const cb = doc.getElementById("feat-" + f.id);
      if (cb.disabled) return false;
      if (!cb.checked) { cb.click(); await wait(5); }
      const r = doc.querySelector(`input[name="var-${f.id}"][value="${o.variant}"]`);
      if (r && !r.checked) { r.click(); await wait(5); }
      return true;
    };
    const reached = new Set(), missing = [];
    for (const [i, f] of feats.entries())
      for (const o of choices(f)) {
        await clear();
        await pick(f, o);
        const one = keyNow();
        reached.add(one);
        if (!app.REF_MAINOS[one]) missing.push(one);
        for (const g of feats.slice(i + 1))
          for (const p of choices(g)) {
            await clear();
            await pick(f, o);
            if (!(await pick(g, p))) continue;
            const k = keyNow();
            reached.add(k);
            if (!app.REF_MAINOS[k]) missing.push(k);
          }
      }
    check(missing.length === 0 && !reached.has(""),
      `the page's singles and pairs are all in the REF_MAINOS sample (${reached.size} combinations)` +
      (missing.length ? `; missing: ${[...new Set(missing)].slice(0, 5).join(", ")}` : ""));
    check(errors.length === 0, "no JS error while ticking every single and pair");
  }

  // 6. Real official OS (notes/49): every combination of REF_MAINOS (each card alone, every pair, the largest ones) is
  // reached by ticking its cards and must match its reference hash; on every build each mod is checked against REF_MODS,
  // so a combination outside the list builds too, mod by mod; and a mod that is not the Python one is refused
  if (REAL_OS) {
    const { w, doc, errors } = await load();
    const app = w.MCFlasherApp;
    app.loadOs(new Uint8Array(fs.readFileSync(REAL_OS)), "model-cycles_OS1.13.syx");
    await wait(20);
    if (REAL_ST) app.loadSyntakt(new Uint8Array(fs.readFileSync(REAL_ST)), ST_NAME);
    await wait(20);
    if (REAL_MD) app.loadMd(new Uint8Array(fs.readFileSync(REAL_MD)), "Elektron_SPS1-1UW_OS1.63.syx");
    await wait(20);
    const needsSt = (key) => /sdvintage|syntakt/.test(key);
    const needsMd = (key) => /md-machines/.test(key);
    const offered = Object.keys(app.REF_MAINOS).filter((k) => (REAL_ST || !needsSt(k)) && (REAL_MD || !needsMd(k)));
    check(Object.keys(app.REF_MODS).length === w.MC_TWEAKS.tweaks.length
      && w.MC_TWEAKS.tweaks.every((x) => app.REF_MODS[x.id] && /^[0-9a-f]{64}$/.test(app.REF_MODS[x.id].w)
        && !!x.append === /^[0-9a-f]{64}$/.test(app.REF_MODS[x.id].p || "")),
      `REF_MODS: the writes of each of the ${w.MC_TWEAKS.tweaks.length} tweaks, and the payload of those that append one`);
    const seen = new Set();
    let idx = -1;
    const mine = () => ++idx % SHARD_N === SHARD_K;   // this part's share of the combinations
    for (const key of Object.keys(app.REF_MAINOS)) {
      if (!REAL_ST && needsSt(key)) continue;          // the real Syntakt engines need the Syntakt OS
      if (!REAL_MD && needsMd(key)) continue;          // the Machinedrum machines need the Machinedrum OS
      if (!mine()) continue;
      await tickKey(w, doc, key);
      const f = app.state.fw;
      seen.add(app.state.buildKey);
      check(app.state.buildKey === key && f && f.kind === "built" && f.ref && f.modsRef,
        `real OS: ${key} matches its reference hash, each mod checked`);
    }
    if (MAIN) {
      // three cards together, not in the sample: built, each mod checked, no whole-firmware reference
      const plain = w.MC_TWEAKS.features.filter((f) => !f.engines && !f.excludes && !f.includes && !f.requires && !f.with)
        .map((f) => f.variants[0].id);
      const three = [...Array(plain.length).keys()].flatMap((i) => [...Array(plain.length).keys()].flatMap((j) =>
        [...Array(plain.length).keys()].map((k) => (i < j && j < k ? [plain[i], plain[j], plain[k]].join("+") : null))))
        .find((k) => k && !app.REF_MAINOS[k]);
      await tickKey(w, doc, three);
      const f = app.state.fw;
      check(three && app.state.buildKey === three && f && f.kind === "built" && !f.ref && f.modsRef
        && /Each mod checked against its reference build/.test(text(doc, "file-status")),
        `real OS: ${three} (not in the sample) builds, each mod checked: ${text(doc, "file-status").slice(0, 80)}`);
    }
    if (SHARD_N === 1)
      check(seen.size === offered.length && offered.every((k) => seen.has(k)),
        `REF_MAINOS: the ${seen.size} combinations of the sample all built` + (REAL_ST ? "" : " (without the Syntakt engines: no Syntakt OS given)") + (REAL_MD ? "" : " (without the Machinedrum machines: no Machinedrum OS given)"));
    else {
      fs.writeFileSync(process.env.SMOKE_SEEN, JSON.stringify({ seen: [...seen], offered }));
      console.log(`  (part ${SHARD_K + 1}/${SHARD_N}: ${seen.size} combinations built; coverage checked over all parts)`);
    }
    check(errors.length === 0, "no JS error with the real OS");
  }
  if (REAL_OS && MAIN) {
    // a mod whose writes or payload differ from the Python ones is refused (fresh page: builds are cached per key)
    const { w, doc, errors } = await load();
    const app = w.MCFlasherApp;
    app.loadOs(new Uint8Array(fs.readFileSync(REAL_OS)), "model-cycles_OS1.13.syx");
    await wait(20);
    const tm = app.REF_MODS["tempo-max"].w, tg = app.REF_MODS["model-tg"].p;
    app.REF_MODS["tempo-max"].w = "0".repeat(64);
    app.REF_MODS["model-tg"].p = "0".repeat(64);
    await tickKey(w, doc, "tempo-max");
    check(!app.state.fw && /tempo-max : ecritures differentes de la reference/.test(app.state.fwError || ""),
      "a mod whose writes differ from REF_MODS is refused: " + app.state.fwError);
    await tickKey(w, doc, "model-tg");
    check(!app.state.fw && /model-tg : charge utile differente de la reference/.test(app.state.fwError || ""),
      "a mod whose payload differs from REF_MODS is refused: " + app.state.fwError);
    app.REF_MODS["tempo-max"].w = tm;
    app.REF_MODS["model-tg"].p = tg;
    check(errors.length === 0, "no JS error when a mod is refused");
  }

  // 7. "Samples OS" tab with both official files
  if (REAL_OS && REAL_SMP && MAIN) {
    const env7 = await load();
    const { w, doc, errors, sent } = env7;
    const app = w.MCFlasherApp;
    const cyc = new Uint8Array(fs.readFileSync(REAL_OS)), smp = new Uint8Array(fs.readFileSync(REAL_SMP));
    doc.getElementById("tab-samples").click();
    await wait(20);
    check(!doc.getElementById("panel-samples").hidden && !doc.getElementById("drop2-wrap").hidden
      && /Load both official OS files/.test(text(doc, "h2s")), "Samples OS tab: panel, second drop zone, step 2 title");
    app.loadSamples(cyc, "model-cycles_OS1.13.syx");               // wrong file in the second zone
    await wait(20);
    check(/not the official Model:Samples OS/.test(text(doc, "file2-status")), "a Cycles file in the Samples zone is refused");
    app.loadOs(smp, "model-samples_OS1.13.syx");                   // wrong file in the first zone
    await settle(w);
    check(/first file must be the official/.test(text(doc, "file-status")) && /first file must be/.test(text(doc, "missing")),
      "a Samples file in the Cycles zone is refused for this tab");
    app.loadOs(cyc, "model-cycles_OS1.13.syx");
    app.loadSamples(smp, "model-samples_OS1.13.syx");
    await settle(w);
    const f = app.state.fw;
    const sha = f && w.MCBuilder.hex(w.MCBuilder.sha256(f.raw));
    check(f && f.kind === "samples" && sha === app.REF_SAMPLES_ON_CYCLES, "both files -> reference build (" + (sha || "").slice(0, 16) + ")");
    check(/Model:Samples OS for your Model:Cycles/.test(text(doc, "file-status")) && /recognised/.test(text(doc, "file2-status")),
      "status lines for both files");
    doc.getElementById("m-slow").click();
    doc.getElementById("allow").click();
    await wait(80);
    doc.getElementById("ack").click();
    await wait(20);
    check(/MIDI interface for the way back/.test(text(doc, "missing")) && doc.getElementById("flash").disabled,
      "flash blocked until the MIDI-interface box is ticked");
    doc.getElementById("samples-ack").click();
    await wait(20);
    check(!doc.getElementById("flash").disabled && /Model:Samples OS \(for Model:Cycles\)/.test(text(doc, "summary")), "then ready: " + text(doc, "summary"));
    doc.getElementById("tab-mods").click();
    await settle(w);
    check(app.state.fw === null && /Select a mod/.test(text(doc, "missing")), "back to Mods: the Samples build is not sent");
    doc.getElementById("tab-samples").click();
    await settle(w);
    doc.getElementById("pace").value = "0";
    doc.getElementById("pace").dispatchEvent(new w.Event("input"));
    const n0 = sent.length;
    doc.getElementById("flash").click();
    for (let i = 0; i < 200 && app.state.sending; i++) await wait(50);
    check(sent.length - n0 === w.MCFlasher.splitMessages(app.state.fw.raw).length && /restarts as a Model:Samples/.test(text(doc, "result")),
      "full transfer + Samples message");
    noRest(w);
    doc.getElementById("m-fast").click();
    await wait(150);
    doc.getElementById("flash").click();
    await untilSent(w);
    check(app.state.finished === "ok" && same(env7.dev.received, app.state.fw.raw) && env7.dev.bad.length === 0
      && /restarts as a Model:Samples/.test(text(doc, "result")), "fast: the Samples OS build reaches the Model:Cycles byte for byte");
    doc.querySelector('.lang button[data-lang="fr"]').click();
    await wait(20);
    check(/OS Samples/.test(text(doc, "tab-samples")) && doc.getElementById("drop2-title").textContent === "model-samples_OS1.13.syx",
      "FR: tab translated, loaded file name kept");
    check(errors.length === 0, "no JS error in the Samples OS flow " + (errors.length ? JSON.stringify(errors) : ""));
  }

  // 7b. "Samples OS" tab, for a Model:Samples: the Cycles OS (notes/41), then its way back, over USB
  if (REAL_OS && REAL_SMP && MAIN) {
    const env = await load({ devName: "Elektron Model:Samples", device: { id: 25, name: "Model Samples" } });
    const { w, doc, errors } = env;
    const app = w.MCFlasherApp;
    const cyc = new Uint8Array(fs.readFileSync(REAL_OS)), smp = new Uint8Array(fs.readFileSync(REAL_SMP));
    doc.getElementById("tab-samples").click();
    doc.getElementById("smp-dir-smp").click();
    await wait(20);
    check(!doc.getElementById("smp-pane-smp").hidden && doc.getElementById("smp-pane-cyc").hidden
      && /Experimental/.test(text(doc, "smp-pane-smp")), "Model:Samples → Cycles OS: its own pane, tagged experimental");
    app.loadOs(cyc, "model-cycles_OS1.13.syx");
    app.loadSamples(smp, "model-samples_OS1.13.syx");
    await settle(w);
    let f = app.state.fw, sha = f && w.MCBuilder.hex(w.MCBuilder.sha256(f.raw));
    check(f && f.kind === "cos" && f.raw[4] === 0x0f && sha === app.REF_CYCLES_ON_SAMPLES,
      "both files -> Cycles OS for Model:Samples, reference build (" + (sha || "").slice(0, 16) + ")");
    doc.getElementById("allow").click();
    await wait(150);
    doc.getElementById("ack").click();
    await wait(20);
    check(/backup/.test(text(doc, "missing")) && doc.getElementById("flash").disabled, "flash blocked until the backup box is ticked");
    doc.getElementById("cos-ack").click();
    await wait(20);
    check(!doc.getElementById("flash").disabled && /Model:Cycles OS \(for Model:Samples\)/.test(text(doc, "summary")),
      "then ready: " + text(doc, "summary"));
    doc.getElementById("flash").click();
    await untilSent(w);
    check(app.state.finished === "ok" && same(env.dev.received, f.raw) && /restarts as a <b>Model:Cycles<\/b>|restarts as a Model:Cycles/.test(text(doc, "result")),
      "fast: the Cycles OS reaches the Model:Samples byte for byte");
    check(/Model:Samples screen/.test(text(doc, "result")), "after sending: confirm on the Model:Samples screen");

    // the machine now answers as a Model:Cycles: the way-there file is refused, the way back is accepted
    env.dev.id = 27;
    doc.getElementById("refresh").click();
    await wait(150);
    check(/nothing to install/.test(text(doc, "midi-status")) && doc.getElementById("flash").disabled,
      "way-there file vs a machine answering Model:Cycles: nothing sent");
    doc.getElementById("smp-dir-back").click();
    await settle(w);
    f = app.state.fw; sha = f && w.MCBuilder.hex(w.MCBuilder.sha256(f.raw));
    check(f && f.kind === "sback" && f.raw[4] === 0x11 && sha === app.REF_SAMPLES_BACK,
      "way back: official Samples OS in the Cycles packing, reference build (" + (sha || "").slice(0, 16) + ")");
    check(same(w.MCBuilder.unwrap(f.raw).stream, w.MCBuilder.unwrap(smp).stream), "way back: same content as the official Samples OS");
    await wait(150);
    check(!doc.getElementById("flash").disabled && /Model:Samples asks/.test(text(doc, "missing")),
      "way back: ready without an extra box: " + text(doc, "missing"));
    doc.getElementById("flash").click();
    await untilSent(w);
    check(app.state.finished === "ok" && same(env.dev.received, f.raw) && /own OS/.test(text(doc, "result")),
      "fast: the way back reaches the machine byte for byte");
    env.dev.id = 25;
    doc.getElementById("refresh").click();
    await wait(150);
    check(/nothing to bring back/.test(text(doc, "midi-status")), "way back vs a machine already on the Samples OS: nothing sent");
    check(errors.length === 0, "no JS error in the Model:Samples flow " + (errors.length ? JSON.stringify(errors) : ""));
  }

  // 7b-bis. Step 3 names the machine being flashed (the tab and machine chosen), and the port after the OS it runs
  {
    const { w, doc, errors } = await load({ devName: "Acme Synth" });
    const app = w.MCFlasherApp;
    noRest(w);
    doc.getElementById("allow").click();
    await wait(150);
    const seen = () => [text(doc, "flash"), text(doc, "midi-status"), doc.querySelector('[data-i18n-html="hf1"]').textContent,
      doc.querySelector('[data-i18n-html="hu3"]').textContent].join(" | ");
    check(/Flash the Model:Cycles/.test(seen()) && /Connect the Model:Cycles/.test(seen()) && /port named “Model:Cycles”/.test(seen())
      && !/Model:Samples/.test(seen()), "Mods tab, Model:Cycles: step 3 names the Model:Cycles: " + text(doc, "midi-status"));
    for (const [m, port] of [["smp", "Model:Samples"], ["cos", "Model:Cycles"]]) {
      doc.getElementById("mach-" + m).click();
      await wait(20);
      check(/Flash the Model:Samples/.test(seen()) && /Connect the Model:Samples/.test(seen()) && /the Model:Samples/i.test(text(doc, "midi-status"))
        && !/the Model:Cycles/i.test(text(doc, "midi-status")) && new RegExp("port named “" + port + "”").test(seen()),
        `Mods tab, ${m}: step 3 names the Model:Samples, port “${port}”: ` + seen());
    }
    app.setMode("samples");
    for (const [d, dev, port] of [["cyc", "Model:Cycles", "Model:Cycles"], ["smp", "Model:Samples", "Model:Samples"], ["back", "Model:Samples", "Model:Cycles"]]) {
      doc.getElementById("smp-dir-" + d).click();
      await wait(20);
      check(new RegExp("Flash the " + dev).test(seen()) && new RegExp("the " + dev, "i").test(text(doc, "midi-status"))
        && new RegExp("port named “" + port + "”").test(seen()), `Samples OS tab, ${d}: names the ${dev}, port “${port}”`);
    }
    app.applyLang("fr");
    await wait(20);
    check(/Flasher le Model:Samples/.test(text(doc, "flash")) && /le Model:Samples/i.test(text(doc, "midi-status")), "in French too: " + text(doc, "midi-status"));
    app.applyLang("en");
    app.setMode("mods");
    doc.getElementById("mach-cyc").click();
    await wait(20);
    check(/Flash the Model:Cycles/.test(seen()) && !errors.length, "back to the Model:Cycles, no JS error " + errors.join(" "));
  }

  // 7c. Mods tab on a Model:Samples (notes/57): always the Model:Cycles OS, packed for the machine. The two files must be
  // byte for byte those of tools/mods_for_samples.py for the same Model-TG build (SHA-256 below, printed by
  // tools/emu/test_mods_for_samples.py).
  if (REAL_OS && REAL_SMP && MAIN) {
    const MFS = { smp: "1985e8e703092b768d32aa2c9b446cb0f95c1f944dc3e206f75973337469f686",
                  cos: "1317199fbc625c38700344b69ce00496cdee0c8be6fae305843e6373e6394d19" };
    const env = await load({ devName: "Elektron Model:Samples", device: { id: 25, name: "Model Samples" } });
    const { w, doc, errors } = env;
    const app = w.MCFlasherApp;
    noRest(w);
    const cyc = new Uint8Array(fs.readFileSync(REAL_OS)), smp = new Uint8Array(fs.readFileSync(REAL_SMP));
    check(app.state.machine === "cyc" && doc.getElementById("mach-pane").hidden && doc.getElementById("drop2-wrap").hidden
      && doc.getElementById("mach-cyc").getAttribute("aria-checked") === "true", "Mods tab: Model:Cycles by default, no Samples pane");
    doc.getElementById("mach-smp").click();
    await wait(20);
    check(!doc.getElementById("mach-pane").hidden && /Tested/.test(text(doc, "mach-pane")) && !doc.getElementById("drop2-wrap").hidden
      && /Load both official OS files/.test(text(doc, "h2s")) && !doc.getElementById("mach-w-smp").hidden
      && doc.getElementById("mach-w-cos").hidden, "Model:Samples on its OS: pane tagged tested, second drop zone");
    app.loadOs(cyc, "model-cycles_OS1.13.syx");
    doc.getElementById("feat-model-tg").click();
    await settle(w);
    check(!app.state.fw && /official Model:Samples OS below/.test(text(doc, "file-status"))
      && /Model:Samples OS file, to load/.test(text(doc, "mod-sel")), "Model-TG ticked, no Samples file yet: asked for it");
    app.loadSamples(smp, "model-samples_OS1.13.syx");
    await settle(w);
    let f = app.state.fw, sha = f && w.MCBuilder.hex(w.MCBuilder.sha256(f.raw));
    check(f && f.kind === "built" && f.machine === "smp" && f.raw[4] === 0x0f && f.ref && f.sha === app.REF_MAINOS["model-tg"]
      && sha === MFS.smp && /_for-samples_smp-os\.syx$/.test(f.name),
      "Model-TG for a Model:Samples on its OS = tools/mods_for_samples.py _smp-os (" + (sha || "").slice(0, 16) + ")");
    check(/Packed for your Model:Samples \(on its own OS\)/.test(text(doc, "file-status")), "status line: " + text(doc, "file-status").slice(-60));
    doc.getElementById("allow").click();
    await wait(150);
    doc.getElementById("ack").click();
    await wait(20);
    check(/backup/.test(text(doc, "missing")) && doc.getElementById("flash").disabled, "flash blocked until the backup box is ticked");
    doc.getElementById("mach-ack").click();
    await wait(20);
    check(!doc.getElementById("flash").disabled && /\(for Model:Samples\)/.test(text(doc, "summary")) && /Model:Samples asks/.test(text(doc, "missing")),
      "then ready: " + text(doc, "summary"));
    doc.getElementById("flash").click();
    await untilSent(w);
    check(app.state.finished === "ok" && same(env.dev.received, f.raw) && /with your mods/.test(text(doc, "result")),
      "fast: the modded Cycles OS reaches the Model:Samples byte for byte");

    // now it answers as a Model:Cycles: the Samples-OS packing is refused, the Cycles-OS packing (change mods) is sent
    env.dev.id = 27;
    doc.getElementById("refresh").click();
    await wait(150);
    check(/already on the Cycles OS/.test(text(doc, "midi-status")) && doc.getElementById("flash").disabled,
      "Samples-OS packing vs a machine answering Model:Cycles: nothing sent");
    doc.getElementById("mach-cos").click();
    await settle(w);
    f = app.state.fw; sha = f && w.MCBuilder.hex(w.MCBuilder.sha256(f.raw));
    check(f && f.machine === "cos" && f.raw[4] === 0x11 && f.raw[8] === 0x0c && sha === MFS.cos && !doc.getElementById("mach-w-cos").hidden,
      "Model:Samples on the Cycles OS = tools/mods_for_samples.py _cyc-os (" + (sha || "").slice(0, 16) + ")");
    await wait(150);
    check(!doc.getElementById("flash").disabled, "ready for a machine answering Model:Cycles: " + text(doc, "missing"));
    doc.getElementById("flash").click();
    await untilSent(w);
    check(app.state.finished === "ok" && same(env.dev.received, f.raw), "fast: the change of mods reaches the machine byte for byte");
    env.dev.id = 25;
    doc.getElementById("refresh").click();
    await wait(150);
    check(/on its own OS/.test(text(doc, "midi-status")) && doc.getElementById("flash").disabled,
      "Cycles-OS packing vs a machine answering Model:Samples: nothing sent");

    // back to Model:Cycles: the usual build, and a machine answering Model:Samples is pointed to step 1
    doc.getElementById("mach-cyc").click();
    await settle(w);
    f = app.state.fw;
    check(f && !f.machine && f.raw[4] === 0x11 && f.sha === app.REF_MAINOS["model-tg"] && doc.getElementById("mach-pane").hidden
      && doc.getElementById("drop2-wrap").hidden && /choose it in step 1/.test(text(doc, "midi-status")),
      "Model:Cycles again: plain build; a Model:Samples answering is told to pick it in step 1");
    doc.querySelector('.lang button[data-lang="fr"]').click();
    doc.getElementById("mach-smp").click();
    await settle(w);
    check(/sous son OS/.test(text(doc, "mach-smp")) && /Des mods sur un Model:Samples/.test(text(doc, "mach-pane"))
      && /Emballé pour votre Model:Samples/.test(text(doc, "file-status")), "FR: machine picker and status translated");
    app.setMachine("cyc");                                         // remembered by the page: leave the default for the next sections
    check(errors.length === 0, "no JS error in the mods-on-Model:Samples flow " + (errors.length ? JSON.stringify(errors) : ""));
  }

  // 8. Syntakt engines with the official Model:Cycles and Syntakt files, up to the transfer
  if (REAL_OS && REAL_ST && MAIN) {
    const { w, doc, errors, sent } = await load();
    const app = w.MCFlasherApp;
    const cyc = new Uint8Array(fs.readFileSync(REAL_OS)), syn = new Uint8Array(fs.readFileSync(REAL_ST));
    app.loadOs(cyc, "model-cycles_OS1.13.syx");
    doc.getElementById("feat-syntakt").click();
    await settle(w);
    app.loadSyntakt(cyc, "model-cycles_OS1.13.syx");               // wrong file in the Syntakt zone
    await settle(w);
    check(!app.state.syntakt && /not the official Syntakt/.test(text(doc, "file3-status")) && !app.state.fw, "a Cycles file in the Syntakt zone is refused");
    app.loadSyntakt(syn, ST_NAME);
    await settle(w);
    const f = app.state.fw;
    check(f && f.kind === "built" && f.ref && f.sdv === "syntakt-sd"
      && text(doc, "file3-status").includes(`Official Syntakt OS ${ST_VERSION} recognised`)
      && /Real Syntakt engines — SDVtg/.test(text(doc, "file-status")), "Syntakt file -> reference build of SDVtg (default) " + (f ? f.name : ""));
    check(new RegExp("MAIN OS " + app.REF_MAINOS["syntakt-sd"].slice(0, 8)).test(text(doc, "file-status")),
      "status line shows the MAIN OS hash prefix: " + text(doc, "file-status").slice(-20));
    doc.getElementById("m-slow").click();
    doc.getElementById("allow").click();
    await wait(80);
    check(/Tick the box/.test(text(doc, "missing")) && doc.getElementById("flash").disabled, "asks for the confirmation box");
    doc.getElementById("ack").click();
    await wait(20);
    check(!doc.getElementById("flash").disabled && doc.getElementById("step-choose").classList.contains("done"), "then ready: " + text(doc, "summary"));
    doc.getElementById("pace").value = "0";
    doc.getElementById("pace").dispatchEvent(new w.Event("input"));
    const n0 = sent.length;
    doc.getElementById("flash").click();
    for (let i = 0; i < 200 && app.state.sending; i++) await wait(50);
    check(sent.length - n0 === w.MCFlasher.splitMessages(app.state.fw.raw).length
      && /after Chord come SDVtg \(SD VINTAGE\)\./.test(text(doc, "result")), "full transfer + SDVtg message: " + text(doc, "result").slice(0, 90));
    doc.querySelector('.lang button[data-lang="fr"]').click();
    await wait(20);
    check(doc.getElementById("drop3-title").textContent === ST_NAME && text(doc, "file3-status").includes(`OS officiel Syntakt ${ST_VERSION} reconnu`),
      "FR: loaded Syntakt file name kept, status translated");
    doc.querySelector('.lang button[data-lang="en"]').click();
    await wait(20);
    const combos = engineCombos(w);
    for (const [variant, msg] of [["syntakt-sd-cp", /after Chord come SDVtg \(SD VINTAGE\), CPVtg \(CP VINTAGE\)\./],
                                  ["syntakt-sd-cp-toy-bits-swarm", /after Chord come SDVtg \(SD VINTAGE\), CPVtg \(CP VINTAGE\), SYToy \(SY TOY\), SYBit \(SY BITS\), SYSwm \(SY SWARM\)\./],
                                  ["syntakt-cp", /after Chord come CPVtg \(CP VINTAGE\)\./]]) {
      await pickEngines(doc, combos[variant]);
      await settle(w);
      const fv = app.state.fw;
      check(fv && fv.ref && fv.sdv === variant && fv.name.endsWith(variant + ".syx"),
        `engines ${combos[variant].join(" + ")} -> reference build ${fv ? fv.name : ""}`);
      const n1 = sent.length;
      doc.getElementById("flash").click();
      for (let i = 0; i < 200 && app.state.sending; i++) await wait(50);
      check(sent.length - n1 === w.MCFlasher.splitMessages(fv.raw).length && msg.test(text(doc, "result")),
        `full transfer + message for ${combos[variant].join(" + ")}`);
    }
    // MACRO ticked too (notes/50): the engines' version with MACRO, and MACRO named last after the transfer
    doc.getElementById("feat-macro").click();
    await settle(w);
    const fm = app.state.fw;
    check(fm && fm.ref && fm.sdv === "syntakt-cp-macro" && fm.name.endsWith("syntakt-cp-macro.syx"),
      `CPVtg + MACRO -> reference build ${fm ? fm.name : ""}`);
    const n2 = sent.length;
    doc.getElementById("flash").click();
    for (let i = 0; i < 200 && app.state.sending; i++) await wait(50);
    check(sent.length - n2 === w.MCFlasher.splitMessages(fm.raw).length
      && /after Chord come CPVtg \(CP VINTAGE\), MACRO \(47 models from Braids\)\./.test(text(doc, "result")),
      "full transfer + message for CPVtg + MACRO: " + text(doc, "result").slice(0, 110));
    doc.getElementById("feat-macro").click();
    await settle(w);
    doc.getElementById("eng-cp").click();
    await settle(w);
    check(!app.state.fw && app.state.fwError === "pick_one" && !doc.getElementById("feat-syntakt").checked,
      "every engine unticked -> no mod left to build");
    check(errors.length === 0, "no JS error in the Syntakt engines flow " + (errors.length ? JSON.stringify(errors) : ""));
  }

  console.log(fail ? `\nFAILED (${fail})` : "\nALL OK");
  process.exit(fail ? 1 : 0);
}
main();
