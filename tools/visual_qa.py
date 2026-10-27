#!/usr/bin/env python3
"""
Visual QA Protocol runner (policies/visual-qa-protocol.md)
==========================================================

Implementacion ejecutable del protocolo obligatorio de QA visual y UX/UI.
Abre la app en un navegador real (tools/visual_qa/collect.js, Playwright +
Chromium), evalua la evidencia de forma deterministica y deja un reporte con
capturas, videos y defectos detectados.

ALCANCE HONESTO:
- Detecta automaticamente lo medible: overflow horizontal, imagenes ampliadas
  por encima de su resolucion (borrosas) o deformadas, touch targets chicos,
  texto chico, errores de consola/pagina, requests rotos, interacciones sin
  efecto o tapadas, movimiento que ignora prefers-reduced-motion, falta de
  video cuando hay animacion, LCP/CLS.
- NO juzga solo la fidelidad al diseno aprobado. Arma la hoja de comparacion
  (referencia vs capturas) y exige una revision (LLM-as-judge o humana)
  registrada con `review`. Sin esa revision el veredicto queda
  PENDING_REVIEW, nunca PASS.
- Sin navegador el veredicto es PENDING. Nunca se aprueba un QA visual que
  no se ejecuto.

Uso:
    python tools/visual_qa.py run --url http://localhost:3000 --project DIR \\
        [--reference ref.png] [--out DIR] [--no-video] [--max-interactions 12]
    python tools/visual_qa.py review --report DIR/report.json --review review.json
    python tools/visual_qa.py gate --project DIR     # para merge/deploy
    python tools/visual_qa.py evaluate --raw raw.json   # re-evaluar sin browser

Veredictos y exit codes:
    PASS            0  sin defectos bloqueantes y fidelidad revisada (o sin referencia)
    FAIL            1  hay defectos CRITICAL/HIGH o fidelidad por debajo del umbral
    PENDING         3  no hubo navegador: QA visual pendiente
    PENDING_REVIEW  3  checks automaticos OK, falta revision de fidelidad

Fail-closed: a diferencia de otros helpers de ATLAS, este no es fail-open. Si
algo impide verificar, el resultado es PENDING o FAIL, nunca PASS.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ATLAS_ROOT = Path(__file__).resolve().parent.parent
COLLECTOR = ATLAS_ROOT / "tools" / "visual_qa" / "collect.js"

PROTOCOL_VERSION = "1.0"
REQUIRED_VIEWPORTS = ("desktop", "tablet", "mobile")   # 1440 / 768 / 390

VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_PENDING = "PENDING"
VERDICT_PENDING_REVIEW = "PENDING_REVIEW"
EXIT_CODES = {VERDICT_PASS: 0, VERDICT_FAIL: 1, VERDICT_PENDING: 3, VERDICT_PENDING_REVIEW: 3}

CRITICAL, HIGH, MEDIUM, LOW = "CRITICAL", "HIGH", "MEDIUM", "LOW"
BLOCKING = (CRITICAL, HIGH)

# Umbrales (documentados en policies/visual-qa-protocol.md §Umbrales)
UPSCALE_TOLERANCE = 1.05        # css px por px fuente; >1.05 = imagen ampliada (borrosa)
MIN_IMAGE_AREA = 96 * 96         # ignora iconos chicos
ASPECT_DISTORTION_MAX = 0.03     # 3% de deformacion
TOUCH_MIN_PX = 44
SMALL_TEXT_PX = 12
LCP_WARN_MS = 4000
CLS_WARN, CLS_FAIL = 0.1, 0.25
FIDELITY_MIN_AVG = 7.0
FIDELITY_MIN_DIMENSION = 5.0
FIDELITY_DIMENSIONS = ("composition", "proportions", "typography", "color", "sharpness", "motion", "interaction")

NOISE_PATTERNS = ("Download the React DevTools", "DevTools", "chrome-extension://", "source map", "sourcemap")


# ============================================================
#  Evaluacion deterministica (sin browser)
# ============================================================

def _finding(severity: str, code: str, viewport: Optional[str], message: str, evidence: Any = None) -> Dict[str, Any]:
    return {"severity": severity, "code": code, "viewport": viewport, "message": message, "evidence": evidence}


def _is_noise(text: str) -> bool:
    return any(p.lower() in (text or "").lower() for p in NOISE_PATTERNS)


def _image_findings(images: List[Dict[str, Any]], vp: str, state: Optional[str] = None) -> List[Dict[str, Any]]:
    out = []
    where = f" (estado tras '{state}')" if state else ""
    for im in images or []:
        r = im.get("rendered") or {}
        if (r.get("w", 0) * r.get("h", 0)) < MIN_IMAGE_AREA:
            continue
        css = im.get("css_px_per_source_px") or 0
        dev = im.get("device_px_per_source_px") or 0
        name = (im.get("src") or "").rsplit("/", 1)[-1]
        ev = {k: im.get(k) for k in ("src", "selector", "natural", "rendered", "fit", "css_px_per_source_px", "device_px_per_source_px")}
        if css > UPSCALE_TOLERANCE:
            out.append(_finding(CRITICAL, "BLURRY_UPSCALED_IMAGE", vp,
                                f"{name} se muestra a {css:.2f}x su resolucion{where}: menos de 1 px fuente por px CSS, se ve borrosa.", ev))
        elif dev > UPSCALE_TOLERANCE * 1.0 and dev > 1.5:
            out.append(_finding(MEDIUM, "NOT_RETINA_SHARP", vp,
                                f"{name} a {dev:.2f} px de pantalla por px fuente{where}: nitida en 1x, blanda en pantallas retina.", ev))
        if (im.get("aspect_distortion") or 0) > ASPECT_DISTORTION_MAX:
            out.append(_finding(HIGH, "DISTORTED_IMAGE", vp,
                                f"{name} deformada {im['aspect_distortion'] * 100:.1f}% (proporcion no respetada){where}.", ev))
    return out


def evaluate(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Convierte la evidencia cruda en findings + veredicto. Pura y testeable."""
    findings: List[Dict[str, Any]] = []

    if raw.get("status") == "BROWSER_UNAVAILABLE":
        return {
            "verdict": VERDICT_PENDING,
            "reason": "QA visual PENDIENTE: no se pudo abrir un navegador. " + (raw.get("reason") or ""),
            "findings": [],
            "summary": {"by_severity": {}, "blocking": 0},
        }

    seen_vps = {v.get("name") for v in raw.get("viewports") or []}
    for req in REQUIRED_VIEWPORTS:
        if req not in seen_vps:
            findings.append(_finding(HIGH, "VIEWPORT_NOT_TESTED", req, f"No se probo el viewport {req}; el protocolo exige desktop, tablet y mobile."))

    any_motion = False
    for v in raw.get("viewports") or []:
        vp = v.get("name")
        if v.get("navigation_error"):
            findings.append(_finding(CRITICAL, "NAVIGATION_FAILED", vp, f"La pagina no cargo: {v['navigation_error']}"))
            continue
        if (v.get("http_status") or 200) >= 400:
            findings.append(_finding(CRITICAL, "HTTP_ERROR", vp, f"La URL respondio {v['http_status']}."))
        m = v.get("metrics") or {}

        for e in v.get("page_errors") or []:
            findings.append(_finding(CRITICAL, "PAGE_ERROR", vp, f"Excepcion no capturada: {e}"))
        for c in v.get("console") or []:
            if _is_noise(c.get("text", "")):
                continue
            if c.get("type") == "error":
                findings.append(_finding(HIGH, "CONSOLE_ERROR", vp, c.get("text", "")[:300], c))
            else:
                findings.append(_finding(LOW, "CONSOLE_WARNING", vp, c.get("text", "")[:300], c))
        for r in v.get("bad_responses") or []:
            url = r.get("url", "")
            if "favicon" in url:
                findings.append(_finding(LOW, "FAVICON_MISSING", vp, f"{r['status']} {url}"))
            elif r.get("status", 0) >= 500:
                findings.append(_finding(CRITICAL, "SERVER_ERROR", vp, f"{r['status']} {url}", r))
            else:
                findings.append(_finding(HIGH, "BROKEN_RESOURCE", vp, f"{r['status']} {url}", r))
        for r in v.get("failed_requests") or []:
            sev = LOW if "ERR_ABORTED" in (r.get("failure") or "") else HIGH
            findings.append(_finding(sev, "REQUEST_FAILED", vp, f"{r.get('failure')} {r.get('url')}", r))

        ov = m.get("overflow") or {}
        if ov.get("has_horizontal_overflow"):
            findings.append(_finding(HIGH, "HORIZONTAL_OVERFLOW", vp,
                                     f"Desborde horizontal: documento de {ov.get('document_width')}px en viewport de {v.get('width')}px.",
                                     ov.get("elements")))

        findings.extend(_image_findings(m.get("images"), vp))

        if v.get("touch") and m.get("small_touch_targets_count"):
            findings.append(_finding(HIGH, "SMALL_TOUCH_TARGETS", vp,
                                     f"{m['small_touch_targets_count']} controles tactiles de menos de {TOUCH_MIN_PX}x{TOUCH_MIN_PX}px.",
                                     m.get("small_touch_targets")))
        if m.get("small_text_count"):
            sev = MEDIUM if v.get("touch") else LOW
            findings.append(_finding(sev, "SMALL_TEXT", vp,
                                     f"{m['small_text_count']} textos de menos de {SMALL_TEXT_PX}px.", m.get("small_text")))

        a11y = m.get("a11y") or {}
        if a11y.get("images_without_alt"):
            findings.append(_finding(MEDIUM, "IMG_WITHOUT_ALT", vp, f"{a11y['images_without_alt']} imagenes sin alt."))
        if a11y.get("h1_count") == 0:
            findings.append(_finding(LOW, "NO_H1", vp, "La pagina no tiene <h1>."))

        perf = m.get("performance") or {}
        if (perf.get("lcp_ms") or 0) > LCP_WARN_MS:
            findings.append(_finding(MEDIUM, "SLOW_LCP", vp, f"LCP {perf['lcp_ms']:.0f}ms (> {LCP_WARN_MS}ms)."))
        cls = perf.get("cls") or 0
        if cls > CLS_FAIL:
            findings.append(_finding(HIGH, "LAYOUT_SHIFT", vp, f"CLS {cls} (> {CLS_FAIL})."))
        elif cls > CLS_WARN:
            findings.append(_finding(MEDIUM, "LAYOUT_SHIFT", vp, f"CLS {cls} (> {CLS_WARN})."))

        motion = v.get("motion") or {}
        if (motion.get("moving_elements") or 0) > 0:
            any_motion = True
            if not v.get("video"):
                findings.append(_finding(HIGH, "VIDEO_EVIDENCE_MISSING", vp,
                                         "La pantalla tiene animacion y no se grabo video: el protocolo exige video como evidencia."))

        no_hover = []
        for it in v.get("interactions") or []:
            label = it.get("name") or it.get("tag")
            out = it.get("outcome")
            if out == "no-observable-effect":
                findings.append(_finding(HIGH, "DEAD_INTERACTION", vp,
                                         f"'{label}' ({it.get('tag')}) no produjo ningun efecto observable al {'tocarlo' if v.get('touch') else 'hacer clic'}.", it))
            elif out == "intercepted":
                findings.append(_finding(HIGH, "INTERACTION_BLOCKED", vp,
                                         f"'{label}' esta tapado por otro elemento y no recibe el clic.", it))
            elif out in ("not-reachable", "error"):
                findings.append(_finding(HIGH, "INTERACTION_UNREACHABLE", vp, f"'{label}' no se pudo accionar: {it.get('error')}", it))
            if it.get("suspicious_href"):
                findings.append(_finding(MEDIUM, "PLACEHOLDER_LINK", vp, f"'{label}' usa href placeholder ('#' o javascript:).", it))
            if it.get("hover_feedback") is False:
                no_hover.append(label)
            st = it.get("state") or {}
            findings.extend(_image_findings(st.get("images"), vp, state=label))
            if (st.get("overflow") or {}).get("has_horizontal_overflow"):
                findings.append(_finding(HIGH, "HORIZONTAL_OVERFLOW", vp, f"Desborde horizontal tras '{label}'.", st["overflow"].get("elements")))
        if no_hover:
            findings.append(_finding(LOW, "NO_HOVER_FEEDBACK", vp,
                                     f"{len(no_hover)} controles sin cambio visual en hover: {', '.join(no_hover[:6])}."))

    rm = raw.get("reduced_motion") or {}
    if rm.get("error"):
        findings.append(_finding(HIGH, "REDUCED_MOTION_NOT_TESTED", "desktop", f"No se pudo probar movimiento reducido: {rm['error']}"))
    elif rm:
        moving = (rm.get("motion") or {}).get("moving_elements") or 0
        if moving > 0:
            findings.append(_finding(HIGH, "REDUCED_MOTION_IGNORED", "desktop",
                                     f"Con prefers-reduced-motion: reduce siguen moviendose {moving} elementos.", rm))
    else:
        findings.append(_finding(HIGH, "REDUCED_MOTION_NOT_TESTED", "desktop", "No se ejecuto la prueba de movimiento reducido."))

    # Dedupe por (code, viewport, message)
    uniq, seen = [], set()
    for f in findings:
        k = (f["code"], f["viewport"], f["message"])
        if k not in seen:
            seen.add(k)
            uniq.append(f)
    order = {CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3}
    uniq.sort(key=lambda f: (order[f["severity"]], f["code"], f["viewport"] or ""))

    by_sev: Dict[str, int] = {}
    for f in uniq:
        by_sev[f["severity"]] = by_sev.get(f["severity"], 0) + 1
    blocking = sum(by_sev.get(s, 0) for s in BLOCKING)
    return {
        "verdict": VERDICT_FAIL if blocking else VERDICT_PASS,
        "findings": uniq,
        "summary": {"by_severity": by_sev, "blocking": blocking, "animated": any_motion},
    }


def task_status(verdict: str) -> str:
    """Estado de la tarea visual segun el veredicto. Solo PASS habilita DONE
    (y aun asi DONE requiere la aprobacion del usuario); todo lo demas es BLOCKED."""
    return "READY_FOR_APPROVAL" if verdict == VERDICT_PASS else "BLOCKED"


def asset_actions(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Assets que no alcanzan la resolucion necesaria: que regenerar y a que tamano.

    Una imagen ampliada no se arregla con CSS: hay que regenerarla. El tamano
    minimo sale del peor caso observado (estado/viewport con mas ampliacion),
    en pixeles de pantalla (css x dsf)."""
    worst: Dict[str, Dict[str, Any]] = {}
    for f in findings:
        if f["code"] not in ("BLURRY_UPSCALED_IMAGE", "NOT_RETINA_SHARP"):
            continue
        ev = f.get("evidence") or {}
        src = ev.get("src")
        nat = ev.get("natural") or {}
        factor = ev.get("device_px_per_source_px") or ev.get("css_px_per_source_px") or 0
        if not src or not nat:
            continue
        cur = worst.get(src)
        if not cur or factor > cur["max_device_px_per_source_px"]:
            worst[src] = {
                "asset": src.rsplit("/", 1)[-1], "src": src,
                "current": f"{nat.get('w')}x{nat.get('h')}",
                "max_device_px_per_source_px": factor,
                "required_min": f"{int(nat.get('w', 0) * factor + 0.999)}x{int(nat.get('h', 0) * factor + 0.999)}",
                "worst_case": f"{f['viewport']}: {f['message']}",
                "blocking": f["severity"] in BLOCKING or bool(cur and cur["blocking"]),
            }
        elif f["severity"] in BLOCKING:
            cur["blocking"] = True
    return sorted(worst.values(), key=lambda x: -x["max_device_px_per_source_px"])


def validate_review(review: Dict[str, Any]) -> List[str]:
    """Errores de forma de una revision de fidelidad. Lista vacia = valida."""
    errs = []
    dims = review.get("dimensions")
    if not isinstance(dims, dict):
        return ["review.dimensions debe ser un objeto {dimension: 0-10}"]
    for d in FIDELITY_DIMENSIONS:
        val = dims.get(d)
        if not isinstance(val, (int, float)) or not 0 <= val <= 10:
            errs.append(f"dimension '{d}' falta o no esta entre 0 y 10")
    if not isinstance(review.get("differences"), list):
        errs.append("review.differences debe ser una lista (vacia si no hay diferencias)")
    if not review.get("reviewer"):
        errs.append("review.reviewer es obligatorio (quien reviso: agente o persona)")
    if not review.get("screenshots_reviewed"):
        errs.append("review.screenshots_reviewed debe listar las capturas comparadas")
    return errs


def apply_review(result: Dict[str, Any], review: Optional[Dict[str, Any]], reference: Optional[str]) -> Dict[str, Any]:
    """Combina el veredicto automatico con la revision de fidelidad."""
    result = dict(result)
    result["findings"] = list(result.get("findings") or [])
    if result["verdict"] == VERDICT_PENDING:
        return result
    if not reference:
        result["fidelity"] = {"status": "NO_REFERENCE"}
        result["findings"].append(_finding(MEDIUM, "NO_REFERENCE", None,
                                           "Sin diseno de referencia: no se comparo contra el diseno aprobado. Si existe uno, pasarlo con --reference."))
        return result
    if not review:
        result["fidelity"] = {"status": "REVIEW_REQUIRED", "reference": reference}
        if result["verdict"] == VERDICT_PASS:
            result["verdict"] = VERDICT_PENDING_REVIEW
        return result
    errs = validate_review(review)
    if errs:
        result["fidelity"] = {"status": "INVALID_REVIEW", "errors": errs}
        if result["verdict"] == VERDICT_PASS:
            result["verdict"] = VERDICT_PENDING_REVIEW
        return result
    dims = review["dimensions"]
    avg = sum(dims[d] for d in FIDELITY_DIMENSIONS) / len(FIDELITY_DIMENSIONS)
    low = [d for d in FIDELITY_DIMENSIONS if dims[d] < FIDELITY_MIN_DIMENSION]
    ok = avg >= FIDELITY_MIN_AVG and not low
    result["fidelity"] = {"status": "PASS" if ok else "FAIL", "average": round(avg, 2), "dimensions": dims,
                          "differences": review["differences"], "reviewer": review["reviewer"], "reference": reference}
    if not ok:
        detail = f"promedio {avg:.1f}/10" + (f"; por debajo de {FIDELITY_MIN_DIMENSION:.0f}: {', '.join(low)}" if low else "")
        result["findings"].insert(0, _finding(HIGH, "FIDELITY_BELOW_THRESHOLD", None,
                                              f"Fidelidad al diseno aprobado insuficiente ({detail}).", review["differences"]))
        result["verdict"] = VERDICT_FAIL
    by_sev: Dict[str, int] = {}
    for f in result["findings"]:
        by_sev[f["severity"]] = by_sev.get(f["severity"], 0) + 1
    result["summary"] = {**result.get("summary", {}), "by_severity": by_sev,
                         "blocking": sum(by_sev.get(s, 0) for s in BLOCKING)}
    return result


# ============================================================
#  Hoja de comparacion contra la referencia
# ============================================================

def build_comparison_sheet(out_dir: Path, reference: Optional[str], viewports: List[str]) -> Optional[str]:
    """Referencia + capturas lado a lado (PIL opcional). Devuelve nombre del archivo."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    tiles = []
    if reference and Path(reference).exists():
        tiles.append(("referencia", Image.open(reference).convert("RGB")))
    for vp in viewports:
        p = out_dir / f"{vp}.png"
        if p.exists():
            tiles.append((vp, Image.open(p).convert("RGB")))
    if not tiles:
        return None
    height = 720
    scaled = [(n, im.resize((max(1, int(im.width * height / im.height)), height))) for n, im in tiles]
    width = sum(im.width for _, im in scaled) + 24 * (len(scaled) + 1)
    sheet = Image.new("RGB", (width, height + 64), (16, 18, 24))
    draw = ImageDraw.Draw(sheet)
    x = 24
    for name, im in scaled:
        sheet.paste(im, (x, 48))
        draw.text((x, 16), name.upper(), fill=(230, 230, 240))
        x += im.width + 24
    name = "comparacion.jpg"
    sheet.save(out_dir / name, quality=85)
    return name


# ============================================================
#  Reporte
# ============================================================

def _git_head(project: Optional[Path]) -> Optional[str]:
    if not project:
        return None
    try:
        r = subprocess.run(["git", "-C", str(project), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def write_report(out_dir: Path, raw: Dict[str, Any], result: Dict[str, Any], meta: Dict[str, Any]) -> Path:
    evidence = []
    for v in raw.get("viewports") or []:
        evidence.append({
            "viewport": v.get("name"), "size": f"{v.get('width')}x{v.get('height')}@{v.get('dsf')}x",
            "screenshot": (v.get("screenshots") or {}).get("viewport"),
            "full_page": (v.get("screenshots") or {}).get("full_page"),
            "video": v.get("video"),
            "states": [it["state"]["screenshot"] for it in v.get("interactions") or [] if it.get("state")],
            "interactions_tested": len(v.get("interactions") or []),
        })
    report = {
        "schema": "atlas.visual-qa.report.v1",
        "protocol_version": PROTOCOL_VERSION,
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        **meta,
        "browser": raw.get("browser"),
        "verdict": result["verdict"],
        "task_status": task_status(result["verdict"]),
        "reason": result.get("reason"),
        "asset_actions": asset_actions(result["findings"]),
        "summary": result.get("summary"),
        "fidelity": result.get("fidelity"),
        "evidence": evidence,
        "reduced_motion": raw.get("reduced_motion"),
        "findings": result["findings"],
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
    return out_dir / "report.json"


def render_markdown(r: Dict[str, Any]) -> str:
    L = [f"# QA visual — {r.get('url')}", "",
         f"**Veredicto: {r['verdict']} · Estado de la tarea: {r.get('task_status')}**" + (f" — {r['reason']}" if r.get("reason") else ""), "",
         f"- Protocolo: v{r.get('protocol_version')} · {r.get('generated_at')}",
         f"- Navegador: {(r.get('browser') or {}).get('engine', 'ninguno')} {(r.get('browser') or {}).get('version', '')}",
         f"- Proyecto: {r.get('project')} · commit `{r.get('git_head')}`",
         f"- Severidades: {json.dumps((r.get('summary') or {}).get('by_severity', {}))}", ""]
    fid = r.get("fidelity") or {}
    if fid:
        L += ["## Fidelidad al diseno aprobado", "", f"- Estado: {fid.get('status')}"]
        if fid.get("average") is not None:
            L.append(f"- Promedio: {fid['average']}/10 · {json.dumps(fid.get('dimensions'))}")
            for d in fid.get("differences") or []:
                L.append(f"  - {d}")
        if r.get("comparison_sheet"):
            L.append(f"- Hoja de comparacion: `{r['comparison_sheet']}`")
        L.append("")
    L += ["## Evidencia", "", "| Viewport | Tamano | Captura | Pagina completa | Video | Estados | Interacciones |", "|---|---|---|---|---|---|---|"]
    for e in r.get("evidence") or []:
        L.append(f"| {e['viewport']} | {e['size']} | `{e['screenshot']}` | `{e['full_page']}` | {('`' + e['video'] + '`') if e.get('video') else '—'} | {len(e['states'])} | {e['interactions_tested']} |")
    rm = r.get("reduced_motion") or {}
    if rm:
        L += ["", f"Movimiento reducido: {(rm.get('motion') or {}).get('moving_elements')} elementos en movimiento · `{rm.get('screenshot')}`"]
    if r.get("asset_actions"):
        L += ["", "## Assets insuficientes (regenerar, no parchear con CSS)", "",
              "| Asset | Actual | Minimo necesario | Peor caso | Bloquea |", "|---|---|---|---|---|"]
        for x in r["asset_actions"]:
            L.append(f"| `{x['asset']}` | {x['current']} | {x['required_min']} | {x['worst_case'].replace('|', '/')} | {'si' if x['blocking'] else 'no'} |")
    L += ["", "## Defectos", ""]
    if not r.get("findings"):
        L.append("Sin defectos detectados.")
    else:
        L += ["| Severidad | Codigo | Viewport | Detalle |", "|---|---|---|---|"]
        for f in r["findings"]:
            L.append(f"| {f['severity']} | {f['code']} | {f['viewport'] or '—'} | {f['message'].replace('|', '/')} |")
    return "\n".join(L) + "\n"


# ============================================================
#  Comandos
# ============================================================

def cmd_run(a: argparse.Namespace) -> int:
    project = Path(a.project).resolve() if a.project else None
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = (project or Path.cwd()) / "qa" / "visual"
    out = Path(a.out).resolve() if a.out else base / stamp
    out.mkdir(parents=True, exist_ok=True)

    node = shutil.which("node")
    if not node:
        raw = {"status": "BROWSER_UNAVAILABLE", "reason": "node no esta en PATH", "viewports": []}
    else:
        cmd = [node, str(COLLECTOR), "--url", a.url, "--out", str(out), "--max-interactions", str(a.max_interactions),
               "--video-seconds", str(a.video_seconds), "--settle-ms", str(a.settle_ms)]
        if not a.no_video:
            cmd.append("--video")
        if project:
            cmd += ["--project", str(project)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=a.timeout)
        raw_path = out / "raw.json"
        if raw_path.exists():
            raw = json.loads(raw_path.read_text(encoding="utf-8"))
        else:
            raw = {"status": "BROWSER_UNAVAILABLE", "reason": f"collector fallo (exit {proc.returncode}): {proc.stderr[-400:]}", "viewports": []}

    result = evaluate(raw)
    review = json.loads(Path(a.review).read_text(encoding="utf-8")) if a.review else None
    result = apply_review(result, review, a.reference)
    meta = {"url": a.url, "project": str(project) if project else None, "git_head": _git_head(project),
            "reference": a.reference, "out_dir": str(out)}
    if a.reference and result["verdict"] != VERDICT_PENDING:
        meta["comparison_sheet"] = build_comparison_sheet(out, a.reference, list(REQUIRED_VIEWPORTS))
    report = write_report(out, raw, result, meta)
    _update_latest(base if not a.out else out.parent, report)
    print(f"[visual-qa] {result['verdict']} ({task_status(result['verdict'])}) — reporte: {report}")
    for f in result["findings"]:
        if f["severity"] in BLOCKING:
            print(f"  [{f['severity']}] {f['code']} ({f['viewport'] or '-'}): {f['message']}")
    return EXIT_CODES[result["verdict"]]


def _update_latest(base: Path, report: Path) -> None:
    try:
        base.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(report, base / "latest.json")
    except Exception:
        pass


def cmd_evaluate(a: argparse.Namespace) -> int:
    raw = json.loads(Path(a.raw).read_text(encoding="utf-8"))
    result = apply_review(evaluate(raw), None, a.reference)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return EXIT_CODES[result["verdict"]]


def cmd_review(a: argparse.Namespace) -> int:
    rp = Path(a.report)
    report = json.loads(rp.read_text(encoding="utf-8"))
    out = rp.parent
    raw = json.loads((out / "raw.json").read_text(encoding="utf-8"))
    review = json.loads(Path(a.review).read_text(encoding="utf-8"))
    result = apply_review(evaluate(raw), review, report.get("reference"))
    meta = {k: report.get(k) for k in ("url", "project", "git_head", "reference", "out_dir", "comparison_sheet")}
    write_report(out, raw, result, meta)
    _update_latest(out.parent, out / "report.json")
    print(f"[visual-qa] {result['verdict']} tras revision de fidelidad — {out / 'report.json'}")
    return EXIT_CODES[result["verdict"]]


def gate_check(project: Path, report_path: Optional[Path] = None) -> Dict[str, Any]:
    """Gate para merge/deploy: exige reporte PASS del commit actual."""
    rp = report_path or (project / "qa" / "visual" / "latest.json")
    if not rp.exists():
        return {"allowed": False, "verdict": VERDICT_PENDING, "reason": f"No hay reporte de QA visual ({rp}). Correr: python tools/visual_qa.py run --url ... --project {project}"}
    try:
        report = json.loads(rp.read_text(encoding="utf-8"))
    except Exception as e:
        return {"allowed": False, "verdict": VERDICT_FAIL, "reason": f"Reporte ilegible: {e}"}
    verdict = report.get("verdict")
    if verdict != VERDICT_PASS:
        return {"allowed": False, "verdict": verdict, "reason": f"Ultimo QA visual = {verdict}. Corregir y volver a inspeccionar antes de merge/deploy."}
    head = _git_head(project)
    if head and report.get("git_head") and head != report["git_head"]:
        return {"allowed": False, "verdict": verdict,
                "reason": f"El reporte PASS es del commit {report['git_head'][:8]} y HEAD es {head[:8]}: re-inspeccionar el codigo actual."}
    return {"allowed": True, "verdict": verdict, "reason": "QA visual PASS para el commit actual."}


def cmd_gate(a: argparse.Namespace) -> int:
    res = gate_check(Path(a.project).resolve(), Path(a.report) if a.report else None)
    print(f"[visual-qa gate] {'OK' if res['allowed'] else 'BLOQUEADO'} — {res['reason']}")
    return 0 if res["allowed"] else 1


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="ATLAS — protocolo obligatorio de QA visual y UX/UI")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="inspeccionar en navegador real y evaluar")
    r.add_argument("--url", required=True)
    r.add_argument("--project", help="carpeta del proyecto (git HEAD + qa/visual/)")
    r.add_argument("--reference", help="imagen del diseno aprobado")
    r.add_argument("--review", help="JSON de revision de fidelidad ya hecha")
    r.add_argument("--out")
    r.add_argument("--no-video", action="store_true")
    r.add_argument("--video-seconds", type=int, default=6)
    r.add_argument("--max-interactions", type=int, default=12)
    r.add_argument("--settle-ms", type=int, default=1500, help="espera tras cargar antes de capturar (ej. intros animadas)")
    r.add_argument("--timeout", type=int, default=900)
    r.set_defaults(fn=cmd_run)
    e = sub.add_parser("evaluate", help="re-evaluar un raw.json sin browser")
    e.add_argument("--raw", required=True)
    e.add_argument("--reference")
    e.set_defaults(fn=cmd_evaluate)
    v = sub.add_parser("review", help="registrar revision de fidelidad y recalcular veredicto")
    v.add_argument("--report", required=True)
    v.add_argument("--review", required=True)
    v.set_defaults(fn=cmd_review)
    g = sub.add_parser("gate", help="exit 0 solo si el ultimo QA visual es PASS para HEAD")
    g.add_argument("--project", required=True)
    g.add_argument("--report")
    g.set_defaults(fn=cmd_gate)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
