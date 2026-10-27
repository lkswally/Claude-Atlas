#!/usr/bin/env python3
"""
Bloque VQA — Protocolo obligatorio de QA visual y UX/UI
=======================================================

Valida policies/visual-qa-protocol.md y su implementacion:

  A. [UNIT]    tools/visual_qa.py evaluate/apply_review/asset_actions/gate_check
               con evidencia sintetica (sin browser).
  B. [HOOK]    .claude/hooks/visual-qa-gate.js bloquea merge/deploy en
               proyectos visuales sin PASS del commit actual.
  C. [WIRING]  CLAUDE.md, agentes, settings template y runtime expected
               referencian la politica; viewports 1440/768/390; dist en sync.
  D. [BROWSER] Chromium real contra dos paginas fixture: una con defectos
               plantados (imagen ampliada, deformada, desborde, boton muerto,
               boton tapado, error de consola, animacion que ignora
               reduced-motion, touch target chico) y una sana. Verifica que
               cada defecto se detecta y que la sana no tiene bloqueantes.
               SKIP (no FAIL) si no hay node/playwright/Chromium.
"""

import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import zlib
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

import visual_qa as vq  # noqa: E402

PASS_COUNT = 0
FAIL_COUNT = 0
SKIP_COUNT = 0


def ok(name, detail=""):
    global PASS_COUNT
    PASS_COUNT += 1
    print(f"  [PASS] {name}{' -- ' + detail if detail else ''}")


def fail(name, detail=""):
    global FAIL_COUNT
    FAIL_COUNT += 1
    print(f"  [FAIL] {name}{' -- ' + detail if detail else ''}")


def skip(name, detail=""):
    global SKIP_COUNT
    SKIP_COUNT += 1
    print(f"  [SKIP] {name}{' -- ' + detail if detail else ''}")


def check(name, cond, detail=""):
    (ok if cond else fail)(name, detail)


def codes(result, viewport=None):
    return {f["code"] for f in result["findings"] if viewport is None or f["viewport"] == viewport}


# ------------------------------------------------------------------
#  A. Unit
# ------------------------------------------------------------------

def vp(name, **over):
    base = {
        "name": name, "width": {"desktop": 1440, "tablet": 768, "mobile": 390}[name], "height": 900,
        "dsf": 1 if name == "desktop" else 2, "touch": name != "desktop",
        "console": [], "page_errors": [], "failed_requests": [], "bad_responses": [],
        "screenshots": {"viewport": f"{name}.png", "full_page": f"{name}-full.png"},
        "video": f"{name}.webm", "http_status": 200,
        "metrics": {"overflow": {"has_horizontal_overflow": False}, "images": [], "small_touch_targets_count": 0,
                    "small_text_count": 0, "a11y": {"h1_count": 1, "images_without_alt": 0}, "performance": {"lcp_ms": 500, "cls": 0}},
        "motion": {"moving_elements": 0}, "interactions": [],
    }
    base.update(over)
    return base


def clean_raw():
    return {"status": "COLLECTED", "viewports": [vp("desktop"), vp("tablet"), vp("mobile")],
            "reduced_motion": {"motion": {"moving_elements": 0}}}


def test_unit():
    print("\n[A] Unit — evaluacion deterministica")
    r = vq.evaluate({"status": "BROWSER_UNAVAILABLE", "reason": "sin chromium"})
    check("A1 sin navegador -> PENDING, nunca PASS", r["verdict"] == vq.VERDICT_PENDING)
    check("A2 sin navegador -> tarea BLOCKED", vq.task_status(r["verdict"]) == "BLOCKED")

    r = vq.evaluate(clean_raw())
    check("A3 evidencia limpia -> PASS automatico", r["verdict"] == vq.VERDICT_PASS, str(codes(r)))

    raw = clean_raw()
    raw["viewports"] = raw["viewports"][:2]
    r = vq.evaluate(raw)
    check("A4 falta viewport mobile -> FAIL VIEWPORT_NOT_TESTED", r["verdict"] == vq.VERDICT_FAIL and "VIEWPORT_NOT_TESTED" in codes(r))

    raw = clean_raw()
    raw["viewports"][0]["metrics"]["images"] = [{"src": "/plate.webp", "natural": {"w": 1000, "h": 500}, "rendered": {"w": 1500, "h": 750},
                                                  "fit": "fill", "css_px_per_source_px": 1.5, "device_px_per_source_px": 1.5, "aspect_distortion": 0}]
    r = vq.evaluate(raw)
    check("A5 imagen ampliada 1.5x -> CRITICAL BLURRY_UPSCALED_IMAGE", "BLURRY_UPSCALED_IMAGE" in codes(r) and r["verdict"] == vq.VERDICT_FAIL)
    acts = vq.asset_actions(r["findings"])
    check("A6 asset_actions pide regenerar plate.webp a >=1500x750",
          acts and acts[0]["asset"] == "plate.webp" and acts[0]["required_min"] == "1500x750" and acts[0]["blocking"], json.dumps(acts))

    raw = clean_raw()
    raw["viewports"][0]["interactions"] = [{"name": "Abrir estacion", "tag": "button", "outcome": "works", "effect": True,
                                            "state": {"screenshot": "s.png", "overflow": {}, "images": [
                                                {"src": "/plate.webp", "natural": {"w": 1520, "h": 1240}, "rendered": {"w": 2232, "h": 1821},
                                                 "fit": "fill", "css_px_per_source_px": 1.468, "device_px_per_source_px": 1.468}]}}]
    r = vq.evaluate(raw)
    check("A7 imagen nitida en reposo pero ampliada tras zoom -> CRITICAL", "BLURRY_UPSCALED_IMAGE" in codes(r))

    raw = clean_raw()
    raw["viewports"][0]["metrics"]["images"] = [{"src": "/a.png", "natural": {"w": 200, "h": 100}, "rendered": {"w": 200, "h": 200},
                                                  "fit": "fill", "css_px_per_source_px": 1.0, "device_px_per_source_px": 1.0, "aspect_distortion": 0.5}]
    check("A8 imagen deformada -> HIGH DISTORTED_IMAGE", "DISTORTED_IMAGE" in codes(vq.evaluate(raw)))

    raw = clean_raw()
    raw["viewports"][2]["metrics"]["overflow"] = {"has_horizontal_overflow": True, "document_width": 620}
    check("A9 desborde horizontal mobile -> HIGH", "HORIZONTAL_OVERFLOW" in codes(vq.evaluate(raw), "mobile"))

    raw = clean_raw()
    raw["viewports"][0]["interactions"] = [{"name": "Nada", "tag": "button", "outcome": "no-observable-effect"},
                                           {"name": "Tapado", "tag": "button", "outcome": "intercepted"}]
    r = vq.evaluate(raw)
    check("A10 boton muerto -> DEAD_INTERACTION", "DEAD_INTERACTION" in codes(r))
    check("A11 boton tapado -> INTERACTION_BLOCKED", "INTERACTION_BLOCKED" in codes(r))

    raw = clean_raw()
    raw["reduced_motion"] = {"motion": {"moving_elements": 12}}
    check("A12 movimiento con reduced-motion -> HIGH", "REDUCED_MOTION_IGNORED" in codes(vq.evaluate(raw)))
    raw = clean_raw()
    raw["reduced_motion"] = None
    check("A13 reduced-motion no probado -> HIGH", "REDUCED_MOTION_NOT_TESTED" in codes(vq.evaluate(raw)))

    raw = clean_raw()
    raw["viewports"][1]["motion"] = {"moving_elements": 30}
    raw["viewports"][1]["video"] = None
    check("A14 animacion sin video -> VIDEO_EVIDENCE_MISSING", "VIDEO_EVIDENCE_MISSING" in codes(vq.evaluate(raw), "tablet"))

    raw = clean_raw()
    raw["viewports"][0]["page_errors"] = ["TypeError: x is undefined"]
    raw["viewports"][0]["console"] = [{"type": "error", "text": "boom"}, {"type": "error", "text": "Download the React DevTools"}]
    r = vq.evaluate(raw)
    check("A15 excepcion -> CRITICAL, console.error -> HIGH, ruido ignorado",
          "PAGE_ERROR" in codes(r) and sum(f["code"] == "CONSOLE_ERROR" for f in r["findings"]) == 1)

    raw = clean_raw()
    raw["viewports"][2]["metrics"]["small_touch_targets_count"] = 3
    check("A16 touch targets chicos en mobile -> HIGH", "SMALL_TOUCH_TARGETS" in codes(vq.evaluate(raw), "mobile"))

    # Fidelidad
    base = vq.evaluate(clean_raw())
    r = vq.apply_review(base, None, "ref.png")
    check("A17 con referencia y sin revision -> PENDING_REVIEW (BLOCKED)", r["verdict"] == vq.VERDICT_PENDING_REVIEW and vq.task_status(r["verdict"]) == "BLOCKED")
    good = {"reviewer": "test", "screenshots_reviewed": ["comparacion.jpg"], "differences": [],
            "dimensions": {d: 8 for d in vq.FIDELITY_DIMENSIONS}}
    r = vq.apply_review(base, good, "ref.png")
    check("A18 revision >= 7 -> PASS / READY_FOR_APPROVAL", r["verdict"] == vq.VERDICT_PASS and vq.task_status(r["verdict"]) == "READY_FOR_APPROVAL")
    bad = dict(good, dimensions={**good["dimensions"], "sharpness": 3}, differences=["plate borroso"])
    r = vq.apply_review(base, bad, "ref.png")
    check("A19 una dimension < 5 -> FAIL FIDELITY_BELOW_THRESHOLD", r["verdict"] == vq.VERDICT_FAIL and "FIDELITY_BELOW_THRESHOLD" in codes(r))
    r = vq.apply_review(base, {"dimensions": {}}, "ref.png")
    check("A20 revision invalida -> no PASS", r["verdict"] == vq.VERDICT_PENDING_REVIEW)
    r = vq.apply_review(vq.evaluate({"status": "BROWSER_UNAVAILABLE"}), good, "ref.png")
    check("A21 una revision no puede aprobar un QA sin navegador", r["verdict"] == vq.VERDICT_PENDING)

    # Gate
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td)
        g = vq.gate_check(proj)
        check("A22 gate sin reporte -> bloquea", not g["allowed"])
        (proj / "qa" / "visual").mkdir(parents=True)
        latest = proj / "qa" / "visual" / "latest.json"
        latest.write_text(json.dumps({"verdict": "FAIL"}))
        check("A23 gate con FAIL -> bloquea", not vq.gate_check(proj)["allowed"])
        latest.write_text(json.dumps({"verdict": "PASS", "git_head": None}))
        check("A24 gate con PASS (sin git) -> permite", vq.gate_check(proj)["allowed"])
        if shutil.which("git"):
            _git_init(proj)
            latest.write_text(json.dumps({"verdict": "PASS", "git_head": "0" * 40}))
            check("A25 gate con PASS de otro commit -> bloquea", not vq.gate_check(proj)["allowed"])
            latest.write_text(json.dumps({"verdict": "PASS", "git_head": vq._git_head(proj)}))
            check("A26 gate con PASS del HEAD -> permite", vq.gate_check(proj)["allowed"])
        else:
            skip("A25-A26 gate vs HEAD", "git no disponible")


def _git_init(d: Path):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "init", "-q", str(d)], check=True, env=env)
    (d / "f.txt").write_text("x")
    subprocess.run(["git", "-C", str(d), "add", "f.txt"], check=True, env=env)
    subprocess.run(["git", "-C", str(d), "commit", "-q", "--no-verify", "-m", "init"], check=True, env=env)


# ------------------------------------------------------------------
#  B. Hook
# ------------------------------------------------------------------

HOOK = PROJECT_ROOT / ".claude" / "hooks" / "visual-qa-gate.js"


def run_hook(payload, env_extra=None):
    env = {k: v for k, v in os.environ.items() if k != "ATLAS_VISUAL_QA_BYPASS"}
    env.update(env_extra or {})
    data = payload if isinstance(payload, str) else json.dumps(payload)
    r = subprocess.run(["node", str(HOOK)], input=data, capture_output=True, text=True, timeout=15, env=env)
    return r.returncode, r.stderr


def test_hook():
    print("\n[B] Hook visual-qa-gate.js")
    if not shutil.which("node"):
        skip("B* hook", "node no disponible")
        return
    with tempfile.TemporaryDirectory() as td:
        ui = Path(td) / "ui"
        ui.mkdir()
        (ui / "package.json").write_text(json.dumps({"dependencies": {"next": "16.0.0", "react": "19.0.0"}}))
        api = Path(td) / "api"
        api.mkdir()
        (api / "package.json").write_text(json.dumps({"dependencies": {"express": "5.0.0"}}))
        merge = lambda cwd: {"tool_name": "Bash", "tool_input": {"command": "gh pr merge 12 --squash"}, "cwd": str(cwd)}

        check("B1 stdin vacio -> exit 0 (fail-open)", run_hook("")[0] == 0)
        check("B2 JSON roto -> exit 0 (fail-open)", run_hook("{no json")[0] == 0)
        check("B3 comando no gateado -> exit 0", run_hook({"tool_name": "Bash", "tool_input": {"command": "npm run build"}, "cwd": str(ui)})[0] == 0)
        check("B4 proyecto no visual -> exit 0", run_hook(merge(api))[0] == 0)
        code, err = run_hook(merge(ui))
        check("B5 merge en proyecto visual sin QA -> BLOCK (exit 2)", code == 2 and "QA visual" in err, err[:120])
        for cmd in ("vercel --prod", "vercel deploy", "netlify deploy --prod", "git push origin main"):
            c, _ = run_hook({"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(ui)})
            check(f"B6 '{cmd}' sin QA -> BLOCK", c == 2)
        c, _ = run_hook({"tool_name": "Bash", "tool_input": {"command": "git push -u origin feature/x"}, "cwd": str(ui)})
        check("B7 push a rama de feature -> permitido", c == 0)
        (ui / "qa" / "visual").mkdir(parents=True)
        latest = ui / "qa" / "visual" / "latest.json"
        latest.write_text(json.dumps({"verdict": "PENDING_REVIEW", "task_status": "BLOCKED"}))
        check("B8 ultimo QA PENDING_REVIEW -> BLOCK", run_hook(merge(ui))[0] == 2)
        latest.write_text(json.dumps({"verdict": "PASS", "git_head": None}))
        check("B9 ultimo QA PASS -> permitido", run_hook(merge(ui))[0] == 0)
        if shutil.which("git"):
            _git_init(ui)
            latest.write_text(json.dumps({"verdict": "PASS", "git_head": "f" * 40}))
            check("B10 PASS de otro commit -> BLOCK", run_hook(merge(ui))[0] == 2)
        latest.write_text(json.dumps({"verdict": "FAIL"}))
        c, err = run_hook(merge(ui), {"ATLAS_VISUAL_QA_BYPASS": "1"})
        check("B11 bypass explicito -> permitido y avisado", c == 0 and "BYPASS" in err)


# ------------------------------------------------------------------
#  C. Wiring
# ------------------------------------------------------------------

def test_wiring():
    print("\n[C] Wiring de la politica")
    pol = PROJECT_ROOT / "policies" / "visual-qa-protocol.md"
    check("C1 politica canonica existe", pol.exists())
    text = pol.read_text(encoding="utf-8") if pol.exists() else ""
    for needle in ("1440", "768", "390", "BLOCKED", "PENDIENTE", "Assets insuficientes", "prefers-reduced-motion"):
        check(f"C2 politica cubre '{needle}'", needle in text)
    claude = (PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    check("C3 CLAUDE.md (always-on) referencia la politica", "policies/visual-qa-protocol.md" in claude)
    for agent in ("evidence-collector", "reality-checker", "orquestador", "git", "deployer", "frontend-developer"):
        body = (PROJECT_ROOT / ".claude" / "agents" / f"{agent}.md").read_text(encoding="utf-8")
        check(f"C4 {agent} referencia la politica", "visual-qa-protocol.md" in body)
    for agent in ("evidence-collector", "reality-checker"):
        body = (PROJECT_ROOT / ".claude" / "agents" / f"{agent}.md").read_text(encoding="utf-8")
        check(f"C5 {agent} usa 1440/390 y no 1280x720/375x667",
              "1440x900" in body and "390x844" in body and "1280x720" not in body and "375x667" not in body)
    tmpl = (PROJECT_ROOT / "templates" / "settings.json").read_text(encoding="utf-8")
    check("C6 templates/settings.json registra visual-qa-gate.js", "visual-qa-gate.js" in tmpl)
    exp = (PROJECT_ROOT / "config" / "atlas.runtime.expected.yaml").read_text(encoding="utf-8")
    check("C7 runtime expected incluye visual-qa-gate.js", "visual-qa-gate.js" in exp)
    dist = PROJECT_ROOT / "hooks" / "visual-qa-gate.js"
    check("C8 hook dist en sync con .claude/hooks", dist.exists() and dist.read_bytes() == HOOK.read_bytes())
    r = subprocess.run([sys.executable, str(PROJECT_ROOT / "tools" / "sync_dist.py"), "--check"], capture_output=True, text=True)
    check("C9 sync_dist --check sin drift", r.returncode == 0, r.stdout[-200:])


# ------------------------------------------------------------------
#  D. Browser real con fixtures
# ------------------------------------------------------------------

def _png(w, h, path):
    rows = []
    for y in range(h):
        row = bytearray([0])
        for x in range(w):
            row += bytes(((x * 255 // max(1, w - 1)), (y * 255 // max(1, h - 1)), 160))
        rows.append(bytes(row))
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + \
        chunk(b"IDAT", zlib.compress(b"".join(rows), 6)) + chunk(b"IEND", b"")
    path.write_bytes(data)


BAD_HTML = """<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>bad</title><style>
body{margin:0;font-family:sans-serif}
.wide{width:2000px;height:20px;background:#c33}
.spin{width:60px;height:60px;background:#36c;animation:s 1s linear infinite}
@keyframes s{to{transform:rotate(360deg)}}
.cover{position:relative}.cover .shield{position:absolute;inset:0;background:transparent}
.tiny{width:30px;height:30px}
</style></head><body>
<h1>Pagina con defectos plantados</h1>
<img id="blurry" src="small.png" alt="ampliada" style="width:800px;height:400px">
<img id="squash" src="small.png" alt="deformada" style="width:300px;height:300px">
<div class="wide"></div>
<div class="spin"></div>
<button id="dead">Nada</button>
<div class="cover"><button id="covered" onclick="this.textContent='ok'">Tapado</button><div class="shield"></div></div>
<button class="tiny" onclick="this.dataset.n=(+this.dataset.n||0)+1;this.textContent=this.dataset.n">+</button>
<script>console.error('error plantado'); setTimeout(()=>{ undefinedFn(); }, 50);</script>
</body></html>"""

GOOD_HTML = """<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>good</title><style>
body{margin:0;font-family:sans-serif;font-size:16px;padding:16px}
img{display:block;width:100%;max-width:600px;height:auto}
.pulse{width:60px;height:60px;background:#3a6;animation:p 1.2s ease-in-out infinite alternate}
@keyframes p{to{transform:scale(1.2)}}
@media (prefers-reduced-motion: reduce){.pulse{animation:none}}
button{min-width:48px;min-height:48px;font-size:16px;background:#eee}
button:hover{background:#ccc}
</style></head><body>
<h1>Pagina sana</h1>
<img src="big.png" alt="nitida" width="2000" height="1000">
<div class="pulse"></div>
<button id="toggle" aria-pressed="false" onclick="const p=this.getAttribute('aria-pressed')==='true';this.setAttribute('aria-pressed',String(!p));document.getElementById('out').textContent=p?'':'activo'">Activar</button>
<p id="out"></p>
</body></html>"""


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def _browser_available():
    if not shutil.which("node"):
        return False, "node no disponible"
    probe = "const m=(()=>{for(const c of [process.env.ATLAS_PLAYWRIGHT_MODULE,'playwright','playwright-core']){if(!c)continue;try{return require(c)}catch(e){}}})();" \
            "if(!m){process.exit(3)};m.chromium.launch().then(b=>b.close()).then(()=>process.exit(0)).catch(()=>process.exit(4))"
    r = subprocess.run(["node", "-e", probe], capture_output=True, text=True, timeout=60)
    if r.returncode == 3:
        return False, "modulo playwright no instalado"
    if r.returncode != 0:
        return False, "Chromium no lanza"
    return True, ""


def test_browser():
    print("\n[D] Browser real (Chromium via Playwright) contra fixtures")
    available, why = _browser_available()
    if not available:
        skip("D* inspeccion real", why + " — en ese entorno el runner devuelve PENDING (cubierto por A1)")
        return
    with tempfile.TemporaryDirectory() as td:
        site = Path(td) / "site"
        site.mkdir()
        _png(200, 100, site / "small.png")
        _png(2000, 1000, site / "big.png")
        (site / "bad.html").write_text(BAD_HTML, encoding="utf-8")
        (site / "good.html").write_text(GOOD_HTML, encoding="utf-8")
        handler = partial(_QuietHandler, directory=str(site))
        srv = HTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        try:
            out_bad = Path(td) / "out-bad"
            rc = vq.main(["run", "--url", f"{base}/bad.html", "--out", str(out_bad), "--video-seconds", "2", "--max-interactions", "6"])
            rep = json.loads((out_bad / "report.json").read_text(encoding="utf-8"))
            found = {f["code"] for f in rep["findings"]}
            check("D1 pagina con defectos -> FAIL / BLOCKED (exit 1)", rc == 1 and rep["verdict"] == "FAIL" and rep["task_status"] == "BLOCKED")
            for code in ("BLURRY_UPSCALED_IMAGE", "DISTORTED_IMAGE", "HORIZONTAL_OVERFLOW", "DEAD_INTERACTION",
                         "INTERACTION_BLOCKED", "CONSOLE_ERROR", "PAGE_ERROR", "REDUCED_MOTION_IGNORED", "SMALL_TOUCH_TARGETS"):
                check(f"D2 detecta {code}", code in found)
            check("D3 asset_actions pide regenerar small.png", any(a["asset"] == "small.png" for a in rep["asset_actions"]))
            files = {p.name for p in out_bad.iterdir()}
            for vpn in vq.REQUIRED_VIEWPORTS:
                check(f"D4 evidencia {vpn}: captura + pagina completa + video",
                      {f"{vpn}.png", f"{vpn}-full.png", f"{vpn}.webm"} <= files)
            check("D5 captura con reduced-motion", "desktop-reduced-motion.png" in files)

            out_good = Path(td) / "out-good"
            rc = vq.main(["run", "--url", f"{base}/good.html", "--out", str(out_good), "--video-seconds", "2", "--max-interactions", "4"])
            rep = json.loads((out_good / "report.json").read_text(encoding="utf-8"))
            blocking = [f"{f['code']}@{f['viewport']}" for f in rep["findings"] if f["severity"] in vq.BLOCKING]
            check("D6 pagina sana -> PASS sin bloqueantes", rc == 0 and rep["verdict"] == "PASS", ", ".join(blocking))
            check("D7 pagina sana -> boton funciona en los 3 viewports",
                  "DEAD_INTERACTION" not in {f["code"] for f in rep["findings"]})
        finally:
            srv.shutdown()


def main():
    print("=" * 60)
    print("Bloque VQA — Protocolo obligatorio de QA visual y UX/UI")
    print("=" * 60)
    test_unit()
    test_hook()
    test_wiring()
    test_browser()
    total = PASS_COUNT + FAIL_COUNT
    print(f"\nRESULTADO: {PASS_COUNT}/{total} PASS, {FAIL_COUNT} FAIL, {SKIP_COUNT} SKIP")
    print(f"PASS={PASS_COUNT} FAIL={FAIL_COUNT}")
    return 1 if FAIL_COUNT else 0


if __name__ == "__main__":
    sys.exit(main())
