#!/usr/bin/env node
/**
 * collect.js — Visual QA browser collector (protocolo policies/visual-qa-protocol.md)
 * ==================================================================================
 *
 * Abre la app en un Chromium REAL (Playwright) y junta evidencia cruda:
 *   - screenshots viewport + full page en desktop 1440, tablet 768, mobile 390
 *   - video por viewport (si --video) para revisar animaciones
 *   - metricas DOM: overflow horizontal, imagenes ampliadas (borrosas) o
 *     deformadas, touch targets, texto chico, fuentes, LCP/CLS
 *   - movimiento: elementos que se mueven con y sin prefers-reduced-motion
 *   - interacciones: hover + click/tap real en cada elemento interactivo y si
 *     produjo algun efecto observable (DOM, URL, scroll, foco, dialogo)
 *   - consola, errores de pagina, requests fallidos / status >= 400
 *
 * NO decide el veredicto: eso lo hace tools/visual_qa.py (deterministico,
 * testeable sin browser). Este script solo observa y escribe raw.json.
 *
 * Uso:
 *   node tools/visual_qa/collect.js --url http://localhost:3000/ruta --out DIR
 *        [--video] [--video-seconds 6] [--max-interactions 12] [--project DIR]
 *        [--viewports desktop,tablet,mobile] [--timeout 45000] [--settle-ms 1500]
 *
 * Exit codes:
 *   0  coleccion completa (raw.json escrito, aunque haya defectos)
 *   3  BROWSER_UNAVAILABLE — no hay modulo playwright o Chromium no lanza.
 *      raw.json igual se escribe con status BROWSER_UNAVAILABLE. El QA visual
 *      queda PENDIENTE: nunca se interpreta como aprobado.
 *   4  error de uso (argumentos)
 *
 * Resolucion de Playwright (primer match):
 *   $ATLAS_PLAYWRIGHT_MODULE, playwright, playwright-core,
 *   <project>/node_modules/playwright, <project>/node_modules/playwright-core
 * Chromium custom: $ATLAS_CHROMIUM_PATH.
 */

'use strict';

const fs = require('fs');
const path = require('path');

const EXIT_OK = 0;
const EXIT_UNAVAILABLE = 3;
const EXIT_USAGE = 4;

const MAX_STATE_SHOTS = 6;
const STATE_SETTLE_MS = 1400;
const RESET_SETTLE_MS = 900;

const VIEWPORTS = {
  desktop: { name: 'desktop', width: 1440, height: 900, dsf: 1, mobile: false, touch: false },
  tablet: { name: 'tablet', width: 768, height: 1024, dsf: 2, mobile: true, touch: true },
  mobile: { name: 'mobile', width: 390, height: 844, dsf: 2, mobile: true, touch: true },
};

// Atributos que cambian solos con animaciones (GSAP/SVG/CSS). No cuentan como
// "efecto" de una interaccion.
const ANIMATION_ATTRS = [
  'style', 'transform', 'd', 'x', 'y', 'cx', 'cy', 'r', 'rx', 'ry', 'points',
  'x1', 'x2', 'y1', 'y2', 'opacity', 'offset', 'stop-color', 'stop-opacity',
  'stroke-dashoffset', 'stroke-dasharray', 'viewBox', 'width', 'height',
  'fill-opacity', 'stroke-opacity', 'filter',
];

function parseArgs(argv) {
  const args = { video: false, videoSeconds: 6, maxInteractions: 12, timeout: 45000, settleMs: 1500, viewports: 'desktop,tablet,mobile' };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    const next = () => argv[++i];
    if (a === '--url') args.url = next();
    else if (a === '--out') args.out = next();
    else if (a === '--project') args.project = next();
    else if (a === '--video') args.video = true;
    else if (a === '--video-seconds') args.videoSeconds = Number(next());
    else if (a === '--max-interactions') args.maxInteractions = Number(next());
    else if (a === '--timeout') args.timeout = Number(next());
    else if (a === '--settle-ms') args.settleMs = Number(next());
    else if (a === '--viewports') args.viewports = next();
    else { args.unknown = a; }
  }
  return args;
}

function loadPlaywright(projectDir) {
  const candidates = [
    process.env.ATLAS_PLAYWRIGHT_MODULE,
    'playwright',
    'playwright-core',
  ];
  if (projectDir) {
    candidates.push(path.join(projectDir, 'node_modules', 'playwright'));
    candidates.push(path.join(projectDir, 'node_modules', 'playwright-core'));
  }
  const tried = [];
  for (const c of candidates) {
    if (!c) continue;
    try {
      const mod = require(c);
      if (mod && mod.chromium) return { mod, from: c, tried };
    } catch (e) {
      tried.push(c);
    }
  }
  return { mod: null, from: null, tried };
}

function writeRaw(out, raw) {
  fs.mkdirSync(out, { recursive: true });
  fs.writeFileSync(path.join(out, 'raw.json'), JSON.stringify(raw, null, 2));
}

// ---------------------------------------------------------------------------
// Codigo que corre dentro de la pagina
// ---------------------------------------------------------------------------

function initScript(animationAttrs) {
  const skip = new Set(animationAttrs);
  const state = { mut: 0, lcp: null, cls: 0 };
  window.__vqa = state;
  const start = () => {
    try {
      new MutationObserver((list) => {
        for (const m of list) {
          if (m.type === 'attributes' && skip.has(m.attributeName)) continue;
          state.mut++;
        }
      }).observe(document.documentElement, { subtree: true, childList: true, attributes: true, characterData: true });
    } catch (_) { /* noop */ }
  };
  if (document.documentElement) start();
  else document.addEventListener('DOMContentLoaded', start);
  try {
    new PerformanceObserver((l) => {
      const e = l.getEntries();
      if (e.length) state.lcp = e[e.length - 1].startTime;
    }).observe({ type: 'largest-contentful-paint', buffered: true });
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) if (!e.hadRecentInput) state.cls += e.value;
    }).observe({ type: 'layout-shift', buffered: true });
  } catch (_) { /* noop */ }
}

async function measurePage({ dsf, touch }) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const root = document.documentElement;

  const short = (el) => {
    if (!el || !el.tagName) return '';
    let s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    const cls = typeof el.className === 'string' ? el.className : (el.className && el.className.baseVal) || '';
    const c = cls.trim().split(/\s+/).filter(Boolean).slice(0, 2);
    if (c.length) s += '.' + c.join('.');
    const label = el.getAttribute && (el.getAttribute('aria-label') || '');
    if (label) s += `[aria-label="${label.slice(0, 40)}"]`;
    return s;
  };
  const isVisible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return false;
    const cs = getComputedStyle(el);
    return cs.visibility !== 'hidden' && cs.display !== 'none' && parseFloat(cs.opacity || '1') > 0.01;
  };
  const rectOf = (el) => {
    const r = el.getBoundingClientRect();
    return { x: Math.round(r.left), y: Math.round(r.top + window.scrollY), w: Math.round(r.width), h: Math.round(r.height) };
  };

  // --- overflow horizontal
  const docWidth = Math.max(root.scrollWidth, document.body ? document.body.scrollWidth : 0);
  const overflowing = [];
  if (docWidth > vw + 1) {
    for (const el of document.body.querySelectorAll('*')) {
      const r = el.getBoundingClientRect();
      if ((r.right > vw + 1 || r.left < -1) && r.width > 0 && r.height > 0) {
        const parent = el.parentElement;
        const pr = parent ? parent.getBoundingClientRect() : null;
        const parentOver = pr && (pr.right > vw + 1 || pr.left < -1);
        if (!parentOver) overflowing.push({ selector: short(el), right: Math.round(r.right), left: Math.round(r.left) });
        if (overflowing.length >= 10) break;
      }
    }
  }

  // --- imagenes (img, svg <image>, background-image)
  const loadNatural = (url) => new Promise((resolve) => {
    const im = new Image();
    im.onload = () => resolve({ w: im.naturalWidth, h: im.naturalHeight });
    im.onerror = () => resolve(null);
    im.src = url;
    setTimeout(() => resolve(null), 5000);
  });
  const isVector = (url) => /\.svg(\?|#|$)/i.test(url || '') || /^data:image\/svg/i.test(url || '');
  const images = [];

  for (const img of document.images) {
    if (!isVisible(img)) continue;
    const src = img.currentSrc || img.src;
    if (isVector(src) || !img.naturalWidth) continue;
    const r = img.getBoundingClientRect();
    const fit = getComputedStyle(img).objectFit || 'fill';
    images.push({ kind: 'img', src, selector: short(img), natural: { w: img.naturalWidth, h: img.naturalHeight }, rendered: { w: r.width, h: r.height }, fit, alt: img.getAttribute('alt') });
  }
  const svgImgs = [...document.querySelectorAll('svg image')].filter(isVisible);
  for (const el of svgImgs) {
    const href = el.getAttribute('href') || el.getAttribute('xlink:href');
    if (!href || isVector(href)) continue;
    const url = new URL(href, document.baseURI).href;
    const nat = await loadNatural(url);
    if (!nat) continue;
    const r = el.getBoundingClientRect();
    const par = (el.getAttribute('preserveAspectRatio') || 'xMidYMid meet');
    const fit = par === 'none' ? 'fill' : (/slice/.test(par) ? 'cover' : 'contain');
    images.push({ kind: 'svg-image', src: url, selector: short(el), natural: nat, rendered: { w: r.width, h: r.height }, fit });
  }
  const bgSeen = new Set();
  for (const el of document.body.querySelectorAll('*')) {
    const bg = getComputedStyle(el).backgroundImage;
    if (!bg || bg === 'none' || !bg.includes('url(')) continue;
    if (!isVisible(el)) continue;
    const m = bg.match(/url\(["']?([^"')]+)["']?\)/);
    if (!m || isVector(m[1])) continue;
    const url = new URL(m[1], document.baseURI).href;
    const key = url + '|' + short(el);
    if (bgSeen.has(key)) continue;
    bgSeen.add(key);
    const nat = await loadNatural(url);
    if (!nat) continue;
    const r = el.getBoundingClientRect();
    const size = getComputedStyle(el).backgroundSize;
    let fit = 'auto';
    if (size === 'cover') fit = 'cover';
    else if (size === 'contain') fit = 'contain';
    else if (/^100% 100%$/.test(size)) fit = 'fill';
    else if (/^100%/.test(size)) fit = 'width';
    images.push({ kind: 'background', src: url, selector: short(el), natural: nat, rendered: { w: r.width, h: r.height }, fit });
    if (images.length > 200) break;
  }
  for (const im of images) {
    const sx = im.rendered.w / im.natural.w;
    const sy = im.rendered.h / im.natural.h;
    let scale;
    if (im.fit === 'cover') scale = Math.max(sx, sy);
    else if (im.fit === 'contain' || im.fit === 'scale-down') scale = Math.min(sx, sy);
    else if (im.fit === 'none' || im.fit === 'auto') scale = 1;
    else if (im.fit === 'width') scale = sx;
    else scale = Math.max(sx, sy);
    if (im.fit === 'scale-down') scale = Math.min(scale, 1);
    im.css_px_per_source_px = Number(scale.toFixed(3));
    im.device_px_per_source_px = Number((scale * dsf).toFixed(3));
    const natAspect = im.natural.w / im.natural.h;
    const renAspect = im.rendered.w / im.rendered.h;
    im.aspect_distortion = im.fit === 'fill' ? Number(Math.abs(renAspect / natAspect - 1).toFixed(3)) : 0;
    im.rendered = { w: Math.round(im.rendered.w), h: Math.round(im.rendered.h) };
  }

  // --- texto chico
  const smallText = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seenParents = new Set();
  while (walker.nextNode()) {
    const t = walker.currentNode;
    if (!t.textContent.trim()) continue;
    const p = t.parentElement;
    if (!p || seenParents.has(p)) continue;
    seenParents.add(p);
    if (!isVisible(p)) continue;
    const fs = parseFloat(getComputedStyle(p).fontSize);
    if (fs < 12) smallText.push({ selector: short(p), font_px: fs, text: t.textContent.trim().slice(0, 40) });
  }

  // --- touch targets
  const interactiveSel = 'a[href],button,[role=button],[role=tab],[role=link],input:not([type=hidden]),select,textarea,summary';
  const smallTargets = [];
  if (touch) {
    for (const el of document.querySelectorAll(interactiveSel)) {
      if (!isVisible(el)) continue;
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      const inlineText = cs.display === 'inline' && el.parentElement && /^(P|LI|SPAN)$/.test(el.parentElement.tagName);
      if (inlineText) continue;
      if (r.width < 44 || r.height < 44) smallTargets.push({ selector: short(el), w: Math.round(r.width), h: Math.round(r.height) });
    }
  }

  // --- tipografia y accesibilidad basica
  const fontOf = (sel) => { const el = document.querySelector(sel); return el ? getComputedStyle(el).fontFamily : null; };
  const loadedFonts = [];
  try { document.fonts.forEach((f) => { if (f.status === 'loaded') loadedFonts.push(f.family.replace(/["']/g, '')); }); } catch (_) { /* noop */ }

  const nav = performance.getEntriesByType('navigation')[0];
  const anims = document.getAnimations ? document.getAnimations() : [];
  let gsapTweens = null;
  try { if (window.gsap && window.gsap.globalTimeline) gsapTweens = window.gsap.globalTimeline.getChildren(true, true, false).length; } catch (_) { /* noop */ }

  return {
    viewport: { width: vw, height: vh, dsf },
    document: { width: docWidth, height: Math.max(root.scrollHeight, document.body ? document.body.scrollHeight : 0) },
    title: document.title,
    overflow: { has_horizontal_overflow: docWidth > vw + 1, document_width: docWidth, elements: overflowing },
    images,
    small_text: smallText.slice(0, 30),
    small_text_count: smallText.length,
    small_touch_targets: smallTargets.slice(0, 30),
    small_touch_targets_count: smallTargets.length,
    typography: { h1: fontOf('h1'), body: fontOf('body'), loaded_fonts: [...new Set(loadedFonts)] },
    a11y: {
      h1_count: document.querySelectorAll('h1').length,
      images_without_alt: [...document.images].filter((i) => !i.hasAttribute('alt')).length,
      lang: root.getAttribute('lang'),
    },
    performance: {
      lcp_ms: window.__vqa ? window.__vqa.lcp : null,
      cls: window.__vqa ? Number(window.__vqa.cls.toFixed(4)) : null,
      dom_content_loaded_ms: nav ? Math.round(nav.domContentLoadedEventEnd) : null,
      load_ms: nav ? Math.round(nav.loadEventEnd) : null,
      transfer_kb: Math.round(performance.getEntriesByType('resource').reduce((a, e) => a + (e.transferSize || 0), 0) / 1024),
    },
    animations: { web_animations: anims.length, infinite: anims.filter((a) => a.effect && a.effect.getTiming && a.effect.getTiming().iterations === Infinity).length, gsap_tweens: gsapTweens },
    rect: rectOf(root),
  };
}

function motionSnapshot() {
  const out = [];
  const els = document.querySelectorAll('body *');
  let i = 0;
  for (const el of els) {
    if (i++ > 4000) break;
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    const cs = getComputedStyle(el);
    out.push([
      Math.round(r.left * 2) / 2, Math.round(r.top * 2) / 2,
      Math.round(r.width), Math.round(r.height),
      cs.transform, cs.opacity, el.getAttribute('transform') || '', (el.getAttribute('d') || '').length,
      cs.strokeDashoffset || '',
    ].join('|'));
  }
  return out;
}

async function sampleMotion(page, waitMs) {
  const a = await page.evaluate(motionSnapshot);
  await page.waitForTimeout(waitMs);
  const b = await page.evaluate(motionSnapshot);
  let moving = 0;
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) if (a[i] !== b[i]) moving++;
  return { sampled_elements: n, moving_elements: moving + Math.abs(a.length - b.length), window_ms: waitMs };
}

// ---------------------------------------------------------------------------
// Interacciones
// ---------------------------------------------------------------------------

function tagInteractives(max) {
  const sel = 'a[href],button,[role=button],[role=tab],[role=link],[onclick],summary,input[type=checkbox],input[type=radio],select,[tabindex]:not([tabindex="-1"])';
  const seen = new Set();
  const list = [];
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none';
  };
  const push = (el, how) => {
    if (seen.has(el) || !visible(el)) return;
    for (const s of seen) if (s.contains(el) || el.contains(s)) return;
    seen.add(el);
    list.push({ el, how });
  };
  for (const el of document.querySelectorAll(sel)) push(el, 'semantic');
  // Elementos clickeables sin semantica (ej. grupos SVG con onClick): cursor pointer.
  for (const el of document.querySelectorAll('body *')) {
    if (list.length >= max * 3) break;
    if (getComputedStyle(el).cursor !== 'pointer') continue;
    const parent = el.parentElement;
    if (parent && getComputedStyle(parent).cursor === 'pointer') continue;
    push(el, 'cursor-pointer');
  }
  return list.slice(0, max).map((x, i) => {
    x.el.setAttribute('data-vqa-id', String(i));
    const name = (x.el.getAttribute('aria-label') || x.el.textContent || x.el.getAttribute('title') || '').trim().replace(/\s+/g, ' ').slice(0, 60);
    const tag = x.el.tagName.toLowerCase();
    return {
      id: String(i), tag, how: x.how, name,
      href: x.el.getAttribute('href'),
      role: x.el.getAttribute('role'),
      aria_expanded: x.el.getAttribute('aria-expanded'),
    };
  });
}

function interactionState() {
  const el = document.activeElement;
  return {
    url: location.href,
    mut: window.__vqa ? window.__vqa.mut : 0,
    scrollY: Math.round(window.scrollY),
    scrollX: Math.round(window.scrollX),
    active: el ? (el.getAttribute('data-vqa-id') || el.tagName) : null,
    dialogs: document.querySelectorAll('dialog[open],[role=dialog],[aria-modal=true]').length,
  };
}

function selfState(id) {
  const el = document.querySelector(`[data-vqa-id="${id}"]`);
  if (!el) return null;
  const attrs = ['aria-pressed', 'aria-expanded', 'aria-selected', 'aria-checked', 'aria-current', 'class', 'open', 'data-state'];
  return attrs.map((a) => `${a}=${el.getAttribute(a)}`).join('|') + `|checked=${el.checked === true}|value=${el.value || ''}`;
}

function hoverStyle(id) {
  const el = document.querySelector(`[data-vqa-id="${id}"]`);
  if (!el) return null;
  const cs = getComputedStyle(el);
  return [cs.color, cs.backgroundColor, cs.transform, cs.boxShadow, cs.opacity, cs.filter, cs.outlineStyle, cs.textDecorationLine, cs.borderColor, cs.scale].join('|');
}

async function probeInteractions(page, url, vp, max, out, settleMs) {
  const items = await page.evaluate(tagInteractives, max);
  const results = [];
  let stateShots = 0;
  for (const it of items) {
    const sel = `[data-vqa-id="${it.id}"]`;
    const res = { ...it, hover_feedback: null, effect: null, outcome: null, error: null };
    try {
      const loc = page.locator(sel).first();
      if (!(await loc.count())) { res.outcome = 'detached'; results.push(res); continue; }
      if (await loc.isDisabled().catch(() => false)) { res.outcome = 'disabled'; results.push(res); continue; }
      const href = it.href || '';
      const isExternal = /^https?:\/\//i.test(href) && !href.startsWith(new URL(url).origin);
      if (isExternal || /^(mailto:|tel:)/i.test(href)) {
        res.outcome = 'link-not-followed';
        res.effect = href.length > 0;
        results.push(res);
        continue;
      }
      if (/^javascript:/i.test(href) || href === '#') res.suspicious_href = true;

      if (!vp.touch) {
        const before = await page.evaluate(hoverStyle, it.id);
        await loc.hover({ timeout: 2500 });
        await page.waitForTimeout(250);
        const after = await page.evaluate(hoverStyle, it.id);
        res.hover_feedback = before !== after;
      }
      // Baseline: cuanta mutacion "sola" hay en la misma ventana (animaciones vivas).
      const b0 = await page.evaluate(interactionState);
      await page.waitForTimeout(450);
      const b1 = await page.evaluate(interactionState);
      const baseline = b1.mut - b0.mut;
      const self0 = await page.evaluate(selfState, it.id);

      const dialogs = [];
      const onDialog = (d) => { dialogs.push(d.message()); d.dismiss().catch(() => {}); };
      page.on('dialog', onDialog);
      if (vp.touch) await loc.tap({ timeout: 2500 });
      else await loc.click({ timeout: 2500 });
      await page.waitForTimeout(450);
      page.off('dialog', onDialog);
      const a1 = await page.evaluate(interactionState).catch(() => null);
      const self1 = a1 ? await page.evaluate(selfState, it.id).catch(() => null) : null;

      if (!a1) {
        res.effect = true; res.outcome = 'navigated';
      } else {
        const delta = a1.mut - b1.mut;
        // El ruido de animaciones es ~constante por ventana: efecto = exceso sobre la linea base.
        const domChanged = baseline === 0 ? delta > 0 : delta > baseline + 2;
        const effects = {
          own_state: self1 !== null && self0 !== self1,
          url: a1.url !== b1.url,
          dom: domChanged,
          scroll: a1.scrollY !== b1.scrollY || a1.scrollX !== b1.scrollX,
          dialog: a1.dialogs !== b1.dialogs || dialogs.length > 0,
          focus_moved: a1.active !== b1.active && a1.active !== it.id && a1.active !== 'BODY',
        };
        res.effects = effects;
        res.mutation_delta = delta;
        res.mutation_baseline = baseline;
        res.effect = Object.values(effects).some(Boolean);
        res.outcome = res.effect ? 'works' : 'no-observable-effect';
        // Estado resultante (ej. zoom a una estacion): captura + re-medicion de
        // imagenes, porque un asset nitido en reposo puede quedar borroso al ampliarse.
        if (res.effect && !effects.url && stateShots < MAX_STATE_SHOTS) {
          stateShots++;
          await page.waitForTimeout(STATE_SETTLE_MS);
          const shot = `${vp.name}-state-${it.id}.png`;
          await page.screenshot({ path: path.join(out, shot) });
          const m = await page.evaluate(measurePage, { dsf: vp.dsf, touch: vp.touch });
          res.state = { screenshot: shot, images: m.images, overflow: m.overflow };
        }
      }
    } catch (e) {
      const msg = String(e && e.message || e);
      res.error = msg.split('\n')[0].slice(0, 300);
      res.outcome = /intercepts pointer events/.test(msg) ? 'intercepted' : (/outside of the viewport|not visible|Timeout/.test(msg) ? 'not-reachable' : 'error');
      const m = msg.match(/<([a-z0-9-]+)[^>]*>[^\n]*intercepts pointer events/i);
      if (m) res.intercepted_by = m[0].slice(0, 160);
    }
    results.push(res);
    // Aislar cada prueba: recargar para que el estado de una interaccion
    // (toggles, paneles abiertos) no contamine la siguiente.
    try {
      await page.goto(url, { waitUntil: 'load', timeout: 20000 });
      await page.waitForTimeout(Math.max(RESET_SETTLE_MS, settleMs));
      await page.evaluate(tagInteractives, max);
    } catch (_) { /* noop */ }
  }
  return results;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function attachListeners(page, sink) {
  page.on('console', (m) => {
    const t = m.type();
    if (t === 'error' || t === 'warning') sink.console.push({ type: t, text: m.text().slice(0, 500), location: m.location() && m.location().url });
  });
  page.on('pageerror', (e) => sink.page_errors.push(String(e && e.message || e).slice(0, 500)));
  page.on('requestfailed', (r) => sink.failed_requests.push({ url: r.url().slice(0, 300), failure: r.failure() && r.failure().errorText, resource: r.resourceType() }));
  page.on('response', (r) => { if (r.status() >= 400) sink.bad_responses.push({ url: r.url().slice(0, 300), status: r.status(), resource: r.request().resourceType() }); });
}

async function runViewport(browser, args, vp, out) {
  const sink = { console: [], page_errors: [], failed_requests: [], bad_responses: [] };
  const ctxOpts = {
    viewport: { width: vp.width, height: vp.height },
    deviceScaleFactor: vp.dsf,
    isMobile: vp.mobile,
    hasTouch: vp.touch,
  };
  const videoDir = path.join(out, '_video_tmp', vp.name);
  if (args.video) ctxOpts.recordVideo = { dir: videoDir, size: { width: vp.width, height: vp.height } };
  const ctx = await browser.newContext(ctxOpts);
  await ctx.addInitScript(initScript, ANIMATION_ATTRS);
  const page = await ctx.newPage();
  attachListeners(page, sink);
  const result = { name: vp.name, width: vp.width, height: vp.height, dsf: vp.dsf, touch: vp.touch, ...sink, screenshots: {} };
  try {
    const resp = await page.goto(args.url, { waitUntil: 'load', timeout: args.timeout });
    result.http_status = resp ? resp.status() : null;
    try { await page.evaluate(() => document.fonts && document.fonts.ready); } catch (_) { /* noop */ }
    await page.waitForTimeout(args.settleMs);
    const vpShot = path.join(out, `${vp.name}.png`);
    await page.screenshot({ path: vpShot });
    const fullShot = path.join(out, `${vp.name}-full.png`);
    await page.screenshot({ path: fullShot, fullPage: true });
    result.screenshots = { viewport: path.basename(vpShot), full_page: path.basename(fullShot) };
    result.metrics = await page.evaluate(measurePage, { dsf: vp.dsf, touch: vp.touch });
    result.motion = await sampleMotion(page, 800);
    if (args.video) await page.waitForTimeout(Math.max(0, args.videoSeconds * 1000 - 800));
    result.interactions = await probeInteractions(page, args.url, vp, args.maxInteractions, out, args.settleMs);
  } catch (e) {
    result.navigation_error = String(e && e.message || e).split('\n')[0].slice(0, 400);
  }
  const video = args.video ? page.video() : null;
  await ctx.close();
  if (video) {
    try {
      const p = await video.path();
      const dest = path.join(out, `${vp.name}.webm`);
      fs.renameSync(p, dest);
      result.video = path.basename(dest);
    } catch (e) { result.video_error = String(e && e.message || e).slice(0, 200); }
  }
  return result;
}

async function runReducedMotion(browser, args, out) {
  const vp = VIEWPORTS.desktop;
  const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, reducedMotion: 'reduce' });
  await ctx.addInitScript(initScript, ANIMATION_ATTRS);
  const page = await ctx.newPage();
  const res = { viewport: vp.name };
  try {
    await page.goto(args.url, { waitUntil: 'load', timeout: args.timeout });
    await page.waitForTimeout(args.settleMs);
    res.matches_reduce = await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches);
    res.motion = await sampleMotion(page, 800);
    const shot = path.join(out, 'desktop-reduced-motion.png');
    await page.screenshot({ path: shot });
    res.screenshot = path.basename(shot);
  } catch (e) {
    res.error = String(e && e.message || e).split('\n')[0].slice(0, 300);
  }
  await ctx.close();
  return res;
}

(async function main() {
  const args = parseArgs(process.argv);
  if (!args.url || !args.out || args.unknown) {
    process.stderr.write(`uso: collect.js --url URL --out DIR [--video] ...${args.unknown ? ` (arg desconocido: ${args.unknown})` : ''}\n`);
    process.exit(EXIT_USAGE);
  }
  const out = path.resolve(args.out);
  const raw = {
    schema: 'atlas.visual-qa.raw.v1',
    url: args.url,
    started_at: new Date().toISOString(),
    status: 'COLLECTED',
    browser: null,
    viewports: [],
    reduced_motion: null,
  };
  const pw = loadPlaywright(args.project);
  if (!pw.mod) {
    raw.status = 'BROWSER_UNAVAILABLE';
    raw.reason = `modulo playwright no encontrado (probados: ${pw.tried.join(', ')}). Instalar: npm i -D playwright && npx playwright install chromium, o setear ATLAS_PLAYWRIGHT_MODULE.`;
    writeRaw(out, raw);
    process.stderr.write(raw.reason + '\n');
    process.exit(EXIT_UNAVAILABLE);
  }
  let browser;
  try {
    const launch = {};
    if (process.env.ATLAS_CHROMIUM_PATH) launch.executablePath = process.env.ATLAS_CHROMIUM_PATH;
    browser = await pw.mod.chromium.launch(launch);
  } catch (e) {
    raw.status = 'BROWSER_UNAVAILABLE';
    raw.reason = `Chromium no lanzo: ${String(e && e.message || e).split('\n')[0]}. Probar: npx playwright install chromium`;
    writeRaw(out, raw);
    process.stderr.write(raw.reason + '\n');
    process.exit(EXIT_UNAVAILABLE);
  }
  raw.browser = { engine: 'chromium', version: browser.version(), playwright_module: pw.from };
  fs.mkdirSync(out, { recursive: true });
  const names = args.viewports.split(',').map((s) => s.trim()).filter(Boolean);
  for (const n of names) {
    const vp = VIEWPORTS[n];
    if (!vp) continue;
    raw.viewports.push(await runViewport(browser, args, vp, out));
  }
  raw.reduced_motion = await runReducedMotion(browser, args, out);
  await browser.close();
  try { fs.rmSync(path.join(out, '_video_tmp'), { recursive: true, force: true }); } catch (_) { /* noop */ }
  raw.finished_at = new Date().toISOString();
  writeRaw(out, raw);
  process.exit(EXIT_OK);
})().catch((e) => {
  process.stderr.write(`collect.js error interno: ${e && e.stack || e}\n`);
  process.exit(1);
});
