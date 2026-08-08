#!/usr/bin/env python
"""Build an attractive MolParetoBO PDF report from current project artifacts."""
from __future__ import annotations

import base64
import subprocess
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
FIG = ROOT / "figures"
DATA = ROOT / "data"
HTML_OUT = ROOT / "MolParetoBO_Report.html"
PDF_OUT = ROOT / "MolParetoBO_Report.pdf"


def b64(path: Path) -> str:
  return base64.b64encode(path.read_bytes()).decode("ascii")


def img_tag(path: Path, alt: str) -> str:
  if not path.exists():
    return f"<p class='muted'>Missing figure: {path.name}</p>"
  ext = path.suffix.lower().lstrip(".") or "png"
  mime = "jpeg" if ext in {"jpg", "jpeg"} else ext
  return (
    f'<figure class="figure">'
    f'<img src="data:image/{mime};base64,{b64(path)}" alt="{alt}"/>'
    f"<figcaption>{alt}</figcaption></figure>"
  )


def family_of(m: str) -> str:
  if m == "SEED":
    return "seed"
  if "methyl_add" in str(m):
    return "methyl_add"
  if "methyl_remove" in str(m):
    return "methyl_remove"
  if "ring_" in str(m):
    return "ring_sub"
  return "other"


def df_to_html(df: pd.DataFrame, float_cols=None) -> str:
  show = df.copy()
  if float_cols:
    for c in float_cols:
      if c in show.columns:
        show[c] = pd.to_numeric(show[c], errors="coerce").map(
          lambda x: f"{x:.3f}" if pd.notna(x) else ""
        )
  return show.to_html(index=False, classes="data", border=0, escape=True)


def main() -> None:
  df = pd.read_csv(DATA / "mutants_scored.csv")
  df["family"] = df["mutation"].map(family_of)
  seed = df.loc[df["mutation"] == "SEED"].iloc[0]
  kept_n = int(df["kept"].sum())
  n = len(df)
  fam = df.groupby("family").agg(n=("mutation", "count"), kept=("kept", "sum")).reset_index()

  metrics = pd.read_csv(DATA / "surrogate_metrics.csv") if (DATA / "surrogate_metrics.csv").exists() else None
  front = pd.read_csv(DATA / "pareto_front.csv") if (DATA / "pareto_front.csv").exists() else None
  hist = pd.read_csv(DATA / "optimization_history.csv") if (DATA / "optimization_history.csv").exists() else None
  front_after = (
    pd.read_csv(DATA / "pareto_front_after_loop.csv")
    if (DATA / "pareto_front_after_loop.csv").exists()
    else None
  )

  today = date.today().strftime("%d %B %Y")
  front_n = len(front) if front is not None else 0
  final_n = len(front_after) if front_after is not None else 0

  ep_html = "".join(
    f"<tr><td>{a}</td><td><strong>{b}</strong></td><td>{c}</td>"
    f"<td><span class='pill'>{d}</span></td><td>{e}</td></tr>"
    for a, b, c, d, e in [
      ("1", "QED", "Drug-likeness", "maximize", "RDKit QED"),
      ("2", "SA", "Synthetic accessibility", "minimize", "RDKit SA Score"),
      ("3", "logP", "Lipophilicity", "prefer ~2.5", "Crippen logP"),
      ("4", "logS", "Aqueous solubility", "maximize", "ESOL-style logS"),
      ("5", "Tox", "Toxicity proxy", "minimize", "Transparent heuristic"),
    ]
  )
  dec_html = "".join(
    f"<tr><td>{a}</td><td><strong>{b}</strong></td><td>{c}</td></tr>"
    for a, b, c in [
      ("Seed", "Ibuprofen", "Build the pipeline"),
      ("Endpoints", "5 objectives", "QED, SA, logP, logS, Tox"),
      ("Mutations", "Methyl and ring edits", "Also applied again to some mutants to make more molecules"),
      ("Filters", "Suitability gates", "sanitize, MW, QED"),
      ("Surrogate", "RF + Morgan FP", "cheap endpoint prediction"),
      ("Acquisition", "quality + uncertainty + diversity", "simplified vs qEHVI"),
      ("Runtime", "Local + Google Colab", "interactive widgets"),
    ]
  )
  fam_html = "".join(
    f"<tr><td>{r.family}</td><td>{int(r.n)}</td><td>{int(r.kept)}</td></tr>"
    for r in fam.itertuples()
  )

  preview = df_to_html(
    df[["mutation", "qed", "sa", "logp", "logs", "tox", "mw", "kept"]].head(12),
    float_cols=["qed", "sa", "logp", "logs", "tox", "mw"],
  )
  metrics_html = df_to_html(metrics, float_cols=["MAE", "R2"]) if metrics is not None else ""
  front_html = (
    df_to_html(
      front[["mutation", "qed", "sa", "logp", "logs", "tox", "mw"]].head(12),
      float_cols=["qed", "sa", "logp", "logs", "tox", "mw"],
    )
    if front is not None
    else ""
  )
  hist_html = (
    df_to_html(
      hist[["iter", "n_labelled", "front_size", "hv_qed_negSA", "batch_mean_acq"]],
      float_cols=["hv_qed_negSA", "batch_mean_acq"],
    )
    if hist is not None
    else ""
  )

  # Cover logos: University of Salerno (left) + partner/project logo (right)
  unisa_path = FIG / "unisa_logo_official.png"
  partner_path = FIG / "partner_logo.png"
  parts = []
  if unisa_path.exists():
    parts.append(
      f'<img class="logo-unisa" src="data:image/png;base64,{b64(unisa_path)}" '
      f'alt="Università degli Studi di Salerno — official logo"/>'
    )
  if partner_path.exists():
    parts.append(
      f'<img class="logo-partner" src="data:image/png;base64,{b64(partner_path)}" '
      f'alt="Project partner logo"/>'
    )
    logo_html = f'<div class="cover-brand">{"".join(parts)}</div>' if parts else ""

    # Contents entries: (anchor, number, label, search_text_in_pdf)
    toc_entries = [
        ("sec-1", "1", "Goal and pipeline", "1. Goal and pipeline"),
        ("sec-2", "2", "Design decisions", "2. Design decisions"),
        ("sec-3", "3", "Seed, endpoints, mutations", "3. Seed, endpoints, mutations"),
        ("sec-4", "4", "Surrogate model", "4. Surrogate model"),
        ("sec-5", "5", "Pareto front", "5. Pareto front"),
        ("sec-6", "6", "Acquisition + iterative loop", "6. Acquisition + iterative loop"),
        ("sec-7", "7", "Critical discussion", "7. Critical discussion"),
        ("sec-8", "8", "Extensions (GP, NSGA-II, EHVI)", "8. Extensions"),
        ("sec-9", "9", "Interactive widgets & tools", "9. Interactive widgets"),
    ]

    def make_toc_html(pages: dict[str, str] | None = None) -> str:
        pages = pages or {}
        rows = []
        for anchor, num, label, _needle in toc_entries:
            pg = pages.get(anchor, "…")
            rows.append(
                f'<li><a href="#{anchor}">'
                f'<span class="n">{num}</span>'
                f'<span class="label">{label}</span>'
                f'<span class="dots"></span>'
                f'<span class="pg">{pg}</span>'
                f"</a></li>"
            )
        return "\n".join(rows)

    toc_html = make_toc_html()

  html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>MolParetoBO Technical Report</title>
<style>
 @import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&family=Source+Serif+4:opsz,wght@8..60,500;8..60,700&display=swap');
 :root {{
  --ink:#15202b; --muted:#5a6a78; --accent:#0a2748; --accent-2:#061a33;
  --line:#d5dee6; --panel:#eef3f6; --good:#0a2748;
 }}
 * {{ box-sizing:border-box; }}
 html,body {{ margin:0; padding:0; color:var(--ink); background:#fff;
  font-family:"Source Sans 3","Avenir Next","Helvetica Neue",sans-serif; font-size:11pt; line-height:1.55; }}
 .page {{ max-width:900px; margin:0 auto; padding:28px 36px 48px; }}
 .cover {{
  min-height:auto; display:block;
  padding:0 0 8px; border:1px solid var(--line); border-radius:18px; overflow:hidden;
  background:
   radial-gradient(1200px 500px at 10% 40%, rgba(10,39,72,.10), transparent 55%),
   radial-gradient(900px 420px at 100% 30%, rgba(6,26,51,.08), transparent 50%),
   linear-gradient(180deg,#f7fafb 0%,#fff 55%);
  page-break-after:always;
  break-after:page;
 }}
 .cover-brand {{
  background: #ffffff;
  padding: 16px 32px 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  border-bottom: 1px solid var(--line);
 }}
 .cover-brand .logo-unisa {{
  height: 72px;
  width: auto;
  max-width: 58%;
  object-fit: contain;
 }}
 .cover-brand .logo-partner {{
  height: 70px;
  width: auto;
  max-width: 26%;
  object-fit: contain;
  border-radius: 10px;
 }}
 .cover-body {{ padding: 18px 36px 6px; }}
 .kicker {{ letter-spacing:.14em; text-transform:uppercase; font-size:.72rem; font-weight:700; color:var(--accent); }}
 .cover h1 {{ font-family:"Source Serif 4",Georgia,serif; font-size:2.1rem; line-height:1.15; margin:8px 0 6px; max-width:14ch; }}
 .cover .subtitle {{ font-size:1.02rem; color:var(--muted); max-width:48ch; margin:0 0 10px; }}
 .meta-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:8px 24px; margin-top:14px; max-width:520px; }}
 .meta-grid div {{ border-top:1px solid var(--line); padding-top:6px; }}
 .meta-grid .label {{ font-size:.68rem; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); }}
 .meta-grid .value {{ font-weight:600; font-size:0.95rem; }}
 .cover-toc {{ padding: 4px 36px 22px; }}
 .cover-toc h2 {{ margin-top: 12px; }}
 .cover-toc .toc {{ margin-bottom: 0; }}
 .status-bar {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:28px; }}
 .chip {{ border:1px solid var(--line); background:rgba(255,255,255,.85); border-radius:999px; padding:6px 12px; font-size:.82rem; font-weight:600; }}
 .chip.done {{ border-color:rgba(10,39,72,.35); color:var(--good); }}
 h2 {{ font-family:"Source Serif 4",Georgia,serif; font-size:1.55rem; margin:34px 0 10px; padding-bottom:6px; border-bottom:2px solid var(--accent); display:inline-block; min-width:40%; scroll-margin-top:16px; }}
 h3 {{ font-size:1.05rem; margin:22px 0 8px; color:var(--accent-2); }}
 p {{ margin:0 0 10px; }}
 .lead {{ font-size:1.05rem; color:var(--muted); max-width:62ch; }}
 .callout {{ background:var(--panel); border-left:4px solid var(--accent); padding:12px 14px; border-radius:0 10px 10px 0; margin:14px 0 18px; }}
 .stats {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:18px 0 8px; }}
 .stat {{ border:1px solid var(--line); border-radius:12px; padding:14px 12px; }}
 .stat .n {{ font-family:"Source Serif 4",Georgia,serif; font-size:1.7rem; font-weight:700; color:var(--accent); line-height:1; }}
 .stat .l {{ margin-top:6px; font-size:.78rem; color:var(--muted); text-transform:uppercase; letter-spacing:.06em; }}
 table.data {{ width:100%; border-collapse:collapse; font-size:.86rem; margin:10px 0 18px; }}
 table.data th {{ text-align:left; background:var(--panel); border-bottom:2px solid var(--line); padding:8px 7px; font-size:.75rem; letter-spacing:.04em; text-transform:uppercase; color:var(--muted); }}
 table.data td {{ border-bottom:1px solid var(--line); padding:7px; vertical-align:top; }}
 table.data tr:nth-child(even) td {{ background:#fafcfd; }}
 .pill {{ display:inline-block; background:rgba(10,39,72,.08); color:var(--accent); border-radius:999px; padding:2px 8px; font-size:.78rem; font-weight:600; }}
 figure.figure {{ margin:16px 0 22px; text-align:center; }}
 figure.figure img {{ max-width:100%; height:auto; border:1px solid var(--line); border-radius:12px; background:#fff; }}
 figcaption {{ margin-top:8px; color:var(--muted); font-size:.88rem; }}
 .flow {{ display:grid; grid-template-columns:repeat(5,1fr); gap:8px; margin:16px 0 8px; }}
 .flow .step {{ background:var(--panel); border-radius:12px; padding:12px 10px; text-align:center; border:1px solid var(--line); }}
 .flow .step strong {{ display:block; font-size:.92rem; }}
 .flow .step span {{ display:block; margin-top:4px; font-size:.75rem; color:var(--muted); }}
 .flow .step.active {{ background:rgba(10,39,72,.08); border-color:rgba(10,39,72,.35); }}
 .toc {{ list-style:none; padding:0; margin:12px 0 28px; max-width:640px; }}
 .toc li {{ margin:0; border-bottom:1px solid var(--line); }}
 .toc a {{
  display:flex; align-items:baseline; gap:10px;
  padding:7px 2px; color:var(--ink); text-decoration:none; font-weight:600;
  font-size: 0.95rem;
 }}
 .toc a:hover {{ color:var(--accent); }}
 .toc a .n {{ color:var(--accent); min-width:1.4rem; }}
 .toc a .label {{ flex:0 1 auto; }}
 .toc a .dots {{ flex:1; border-bottom:1px dotted #b7c4ce; margin:0 6px 5px; min-width:20px; }}
 .toc a .pg {{ color:var(--ink); font-variant-numeric:tabular-nums; min-width:1.6rem; text-align:right; }}
 .footer {{ margin-top:40px; padding-top:12px; border-top:1px solid var(--line); color:var(--muted); font-size:.82rem; }}
 @media print {{
  .page {{ max-width:none; padding:0; }}
  .cover {{ min-height:auto; border:none; border-radius:0; page-break-after:always; break-after:page; }}
  figure, table, .stats, .flow {{ page-break-inside:avoid; }}
  .toc a {{ color: var(--ink); }}
  a {{ color: inherit; }}
 }}
</style>
</head>
<body>
<section class="cover" id="cover">
 {logo_html}
 <div class="cover-body">
 <div>
  <div class="kicker">University of Salerno · Master in AI for Drug Discovery</div>
  <h1>MolParetoBO</h1>
  <p class="subtitle">Surrogate-assisted multi-objective molecular optimization — living technical report</p>
    <div class="meta-grid">
      <div><div class="label">Student</div><div class="value">Ali Ghiami</div></div>
      <div><div class="label">Project</div><div class="value">Project 06 · MolParetoBO</div></div>
      <div><div class="label">Document</div><div class="value">Technical report</div></div>
      <div><div class="label">Date</div><div class="value">{today}</div></div>
    </div>
  </div>
  </div>
  <div class="cover-toc">
    <h2 id="contents">Contents</h2>
    <ol class="toc">
{toc_html}
    </ol>
  </div>
</section>

<div class="page">

<h2 id="sec-1">1. Goal and pipeline</h2>
<div class="flow">
 <div class="step active"><strong>1 · Mutate</strong><span>RDKit</span></div>
 <div class="step active"><strong>2 · Filter</strong><span>suitability</span></div>
 <div class="step active"><strong>3 · Score</strong><span>5 endpoints</span></div>
 <div class="step active"><strong>4 · Surrogate</strong><span>RF + fingerprints</span></div>
 <div class="step active"><strong>5 · Pareto</strong><span>acquire next</span></div>
</div>
<div class="callout">Expensive oracles cannot score every mutant. The surrogate proposes cheap predictions; acquisition chooses which molecules deserve a true oracle call.</div>

<h2 id="sec-2">2. Design decisions</h2>
<table class="data"><thead><tr><th>Item</th><th>Decision</th><th>Rationale</th></tr></thead><tbody>{dec_html}</tbody></table>

<h2 id="sec-3">3. Seed, endpoints, mutations</h2>
<div class="stats">
 <div class="stat"><div class="n">{seed['mw']:.0f}</div><div class="l">Seed MW</div></div>
 <div class="stat"><div class="n">{seed['qed']:.2f}</div><div class="l">Seed QED</div></div>
 <div class="stat"><div class="n">{n}</div><div class="l">Molecules scored</div></div>
 <div class="stat"><div class="n">{kept_n}</div><div class="l">Passed filters</div></div>
</div>
<p><strong>SMILES:</strong> <code>{seed['smiles']}</code></p>
{img_tag(FIG / "01_ibuprofen_atom_indices.png", "Figure 1. Ibuprofen with atom indices.")}
<table class="data"><thead><tr><th>#</th><th>Symbol</th><th>Meaning</th><th>Goal</th><th>Oracle</th></tr></thead><tbody>{ep_html}</tbody></table>
<p><strong>Suitability after mutation:</strong> sanitize · deduplicate · MW 150–450 · heavy atoms ≥ 8 · QED ≥ 0.3.</p>
<table class="data"><thead><tr><th>Family</th><th>Generated</th><th>Kept</th></tr></thead><tbody>{fam_html}</tbody></table>
{img_tag(FIG / "02_mutation_gallery.png", "Figure 2. Mutation gallery (seed + kept neighbours).")}
<h3>Scored preview</h3>
{preview}

<h2 id="sec-4">4. Surrogate model</h2>
<p>Morgan fingerprints (radius 2, 2048 bits) → multi-output Random Forest for QED, SA, logP, logS, Tox.</p>
{metrics_html}
{img_tag(FIG / "03_surrogate_parity.png", "Figure 3. Surrogate vs oracle (held-out parity).")}

<h2 id="sec-5">5. Pareto front</h2>
<p>Objectives maximized after sign flips: +QED, −SA, −|logP−2.5|, +logS, −Tox. Non-dominated molecules form the approximate front.</p>
<div class="stats">
 <div class="stat"><div class="n">{front_n}</div><div class="l">Front size (all kept)</div></div>
 <div class="stat"><div class="n">{final_n}</div><div class="l">Front after active loop</div></div>
 <div class="stat"><div class="n">5</div><div class="l">Objectives</div></div>
 <div class="stat"><div class="n">2D</div><div class="l">HV monitor</div></div>
</div>
{img_tag(FIG / "04_pareto_front.png", "Figure 4. Pareto projections in endpoint space.")}
<h3>Front preview</h3>
{front_html}

<h2 id="sec-6">6. Acquisition + iterative loop</h2>
<p>Acquisition = α·quality + β·uncertainty + γ·diversity (defaults 0.5 / 0.3 / 0.2). Each iteration selects a batch, adds oracle labels, retrains the surrogate, and updates the front.</p>
{hist_html}
{img_tag(FIG / "05_optimization_progress.png", "Figure 5. Active-loop progress (front size and 2D hypervolume proxy).")}
<div class="callout">
<strong>Interactive widgets in the notebook:</strong> tune QED filter, run pipeline, query surrogate, and adjust acquisition weights (α, β, γ) live — on local Jupyter or Google Colab.
</div>

<h2 id="sec-7">7. Critical discussion</h2>
<p><strong>Scientific question:</strong> can a small surrogate-assisted loop expose trade-offs among drug-likeness, SA, lipophilicity, solubility and a toxicity proxy from one public seed? <strong>Yes</strong>, as a transparent proof of concept.</p>
<ul>
 <li><strong>Interpretation:</strong> Pareto molecules are undominated compromises, not “the best drug”.</li>
 <li><strong>AI relevance:</strong> fingerprints + learning surrogate + active multi-objective selection.</li>
 <li><strong>Assumptions:</strong> computational oracles; pedagogical tox; local mutations; RF variance as uncertainty.</li>
 <li><strong>Limits:</strong> no wet-lab truth; small neighbourhood; 2D HV proxy; scalar acquisition ≠ hypervolume-optimal.</li>
 <li><strong>SoftMining link:</strong> same industrial pattern (multi-objective design + selective expensive evaluation) at teaching scale.</li>
</ul>

<h2 id="sec-8">8. Extensions — GP, NSGA-II, EHVI</h2>
<p>Beyond the minimal project: runnable upgrades that point toward research-grade Bayesian optimization.</p>
<div class="stats">
 <div class="stat"><div class="n">GP</div><div class="l">PCA + uncertainty</div></div>
 <div class="stat"><div class="n">NSGA</div><div class="l">Crowding subset</div></div>
 <div class="stat"><div class="n">EHVI</div><div class="l">2D MC demo</div></div>
 <div class="stat"><div class="n">qEHVI</div><div class="l">Future (BoTorch)</div></div>
</div>
{img_tag(FIG / "06_gp_uncertainty.png", "Figure 6. GP extension: mean predictive uncertainty by endpoint.")}
{img_tag(FIG / "07_nsga_subset.png", "Figure 7. NSGA-II non-dominated sorting + crowding on the mutant pool.")}
{img_tag(FIG / "08_ehvi_picks.png", "Figure 8. 2D EHVI suggestions relative to the current front.")}
<div class="callout">
<strong>Presentation:</strong> use <code>MolParetoBO_Slides.pdf</code> / <code>MolParetoBO_Slides.pptx</code> (about 12 slides, 10–15 min). Regenerate with <code>python build_slides.py</code>.
</div>

<h2 id="sec-9">9. Interactive widgets &amp; tools</h2>
<p>The notebook includes interactive <strong>ipywidgets</strong> so you can verify runnability without editing code.</p>
<h3>Interactive Control Panel (Section 8c)</h3>
<table class="data">
<thead><tr><th>Button</th><th>What is checked</th></tr></thead>
<tbody>
<tr><td><strong>1 · Run filter check</strong></td><td>Mutations + suitability filters</td></tr>
<tr><td><strong>2 · Inspect molecule</strong></td><td>Structure drawing + oracle endpoints</td></tr>
<tr><td><strong>3 · Query surrogate</strong></td><td>Fingerprint → RF vs oracle</td></tr>
<tr><td><strong>4 · Select batch</strong></td><td>Acquisition ranking (α/β/γ)</td></tr>
<tr><td><strong>5 · Pareto summary</strong></td><td>Front size + HV proxy</td></tr>
</tbody>
</table>
<p>Earlier widgets also exist in Sections 5b (pipeline), 6 (surrogate), and 8b (acquisition weights).</p>

<h3>Tools used (summary)</h3>
<table class="data">
<thead><tr><th>Tool</th><th>Role</th></tr></thead>
<tbody>
<tr><td><strong>RDKit</strong></td><td>SMILES, mutations, QED/logP/MW, fingerprints, drawings; SA Score via Contrib</td></tr>
<tr><td><strong>scikit-learn</strong></td><td>Random Forest surrogate; PCA + Gaussian Process (extension); metrics</td></tr>
<tr><td><strong>pymoo</strong></td><td>NSGA-II non-dominated sorting / crowding (extension)</td></tr>
<tr><td><strong>NumPy / pandas / matplotlib</strong></td><td>Numerics, tables, figures; custom 2D EHVI demo</td></tr>
<tr><td><strong>ipywidgets + Jupyter/Colab</strong></td><td>Interactive checks</td></tr>
<tr><td><strong>python-pptx + Chrome PDF</strong></td><td>Slides and styled report export</td></tr>
</tbody>
</table>
<p>Full version table and oracle method details: <strong>Appendix B</strong> in the notebook.</p>

<div class="footer">Companion: MolParetoBO_Report.ipynb · slides: MolParetoBO_Slides.pdf · {today}</div>
</div>
</body>
</html>
"""
  HTML_OUT.write_text(html, encoding="utf-8")
  print("Wrote", HTML_OUT)

  def chrome_pdf(html_path: Path, pdf_path: Path) -> None:
    chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    subprocess.run(
      [
        str(chrome),
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}",
        html_path.as_uri(),
      ],
      check=True,
      capture_output=True,
    )

  def find_toc_pages(pdf_path: Path) -> dict[str, str]:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    found: dict[str, str] = {}
    for i, page in enumerate(reader.pages, start=1):
      text = page.extract_text() or ""
      # normalize whitespace/newlines from PDF extraction
      flat = " ".join(text.split())
      for anchor, _num, _label, needle in toc_entries:
        if anchor in found:
          continue
        if needle in text or needle in flat:
          found[anchor] = str(i)
    return found

  def stamp_page_numbers(pdf_path: Path) -> None:
    from io import BytesIO
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas as rl_canvas

    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    for i, page in enumerate(reader.pages, start=1):
      box = page.mediabox
      w, h = float(box.width), float(box.height)
      buf = BytesIO()
      c = rl_canvas.Canvas(buf, pagesize=(w, h))
      c.setFont("Helvetica", 9)
      c.setFillColorRGB(0.35, 0.42, 0.47)
      label = f"{i}"
      c.drawCentredString(w / 2.0, 28, label)
      c.save()
      buf.seek(0)
      overlay = PdfReader(buf).pages[0]
      page.merge_page(overlay)
      writer.add_page(page)
    # preserve internal links/annotations from original where possible
    with open(pdf_path, "wb") as f:
      writer.write(f)

  tmp_pdf = ROOT / "_toc_pass.pdf"
  chrome_pdf(HTML_OUT, tmp_pdf)
  pages = find_toc_pages(tmp_pdf)
  print("TOC pages:", pages)

  # Second pass: HTML with real page numbers in Contents
  toc_html = make_toc_html(pages)
  html = html.replace("{toc_html}", toc_html) if "{toc_html}" in html else html
  # Rebuild body TOC by regenerating from template pieces is safer: rewrite file from make_toc
  # Since html already embedded first-pass toc_html, replace the <ol class="toc">...</ol> block.
  import re

  toc_block = "<ol class=\"toc\">\n" + make_toc_html(pages) + "\n</ol>"
  html2 = re.sub(r'<ol class="toc">.*?</ol>', toc_block, html, count=1, flags=re.S)
  HTML_OUT.write_text(html2, encoding="utf-8")
  chrome_pdf(HTML_OUT, PDF_OUT)
  stamp_page_numbers(PDF_OUT)
  if tmp_pdf.exists():
    tmp_pdf.unlink()
  print("Wrote", PDF_OUT, PDF_OUT.stat().st_size)


if __name__ == "__main__":
  main()
