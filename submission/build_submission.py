from __future__ import annotations

import html
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
ASSETS = ROOT / "submission-assets"
WKHTMLTOPDF = Path(r"D:\odooo workshop\wkhtmltopdf\bin\wkhtmltopdf.exe")


def document(title: str, body: str) -> str:
    return f"""<!doctype html>
<html><head><meta charset=\"utf-8\"><title>{html.escape(title)}</title>
<style>
@page {{ size: A4; margin: 14mm; }}
* {{ box-sizing: border-box; }} body {{ font-family: Arial, Helvetica, sans-serif; color:#172126; font-size:10.2pt; line-height:1.43; margin:0; }}
h1 {{ font-size:25pt; letter-spacing:-.6px; margin:0 0 5px; color:#123d3a; }} h2 {{ font-size:15pt; margin:17px 0 7px; color:#0b6861; }} h3 {{ font-size:11pt; margin:10px 0 3px; color:#123d3a; }}
p {{ margin:4px 0 8px; }} ul, ol {{ margin:4px 0 8px; padding-left:20px; }} li {{ margin:2px 0; }}
.top {{ border-bottom:2px solid #17a99b; padding-bottom:9px; margin-bottom:13px; }} .eyebrow {{ color:#0b6861; text-transform:uppercase; letter-spacing:1.25px; font-size:8pt; font-weight:700; }}
.sub {{ color:#506169; font-size:10pt; }} .tag {{ display:inline-block; padding:3px 7px; border-radius:10px; background:#e6f6f1; color:#087268; font-size:8pt; font-weight:bold; margin-right:4px; }}
.grid {{ display:table; width:100%; border-spacing:8px; margin:0 -8px; }} .card {{ display:table-cell; width:33.33%; background:#f5f9f8; border:1px solid #d7e7e3; border-radius:7px; padding:10px; vertical-align:top; }}
table {{ width:100%; border-collapse:collapse; margin:7px 0 10px; font-size:9.2pt; }} th {{ text-align:left; background:#123d3a; color:white; padding:6px; }} td {{ border-bottom:1px solid #dbe6e3; padding:5px 6px; vertical-align:top; }}
.callout {{ background:#ecf8f5; border-left:4px solid #15a393; padding:9px 11px; margin:10px 0; }} .note {{ background:#fff8df; border-left:4px solid #e1aa25; padding:9px 11px; margin:10px 0; }}
.page {{ min-height:267mm; position:relative; page-break-after:always; }} .page:last-child {{ page-break-after:auto; }} .footer {{ position:absolute; bottom:0; left:0; right:0; color:#6c7c80; font-size:8pt; border-top:1px solid #dbe6e3; padding-top:5px; }}
.shot {{ width:100%; border:1px solid #cfe0dc; border-radius:7px; margin:8px 0 4px; }} .caption {{ color:#506169; font-size:9pt; margin-bottom:11px; }}
.mock {{ border:1px solid #cfe0dc; border-radius:7px; overflow:hidden; margin:8px 0; }} .mock-head {{ background:#123d3a; color:white; padding:8px 12px; font-size:9pt; }} .mock-body {{ padding:12px; background:#f6fbfa; }}
.kpi {{ font-weight:bold; color:#087268; font-size:16pt; }} code {{ font-size:8.6pt; background:#edf4f2; padding:1px 3px; }}
</style></head><body>{body}</body></html>"""


def header(label: str, subtitle: str) -> str:
    return f"""<div class=\"top\"><div class=\"eyebrow\">Srujana 2026 · Prompt to Product</div><h1>Campus Chakra</h1><div class=\"sub\">{label} · {subtitle}</div></div>"""


def write(name: str, source: str) -> Path:
    target = OUT / name
    target.write_text(source, encoding="utf-8")
    return target


def render(html_file: Path, pdf_name: str) -> None:
    subprocess.run([
        str(WKHTMLTOPDF), "--enable-local-file-access", "--page-size", "A4",
        "--margin-top", "10mm", "--margin-right", "12mm", "--margin-bottom", "10mm", "--margin-left", "12mm",
        "--encoding", "utf-8", str(html_file), str(OUT / pdf_name),
    ], check=True)


def build_workbook() -> Path:
    body = header("Prompt Workbook", "Prompt iterations, tools, evidence and human decisions") + """
<div class=\"callout\"><b>Purpose.</b> This workbook documents how Campus Chakra was shaped through iterative prompting, implementation and validation. It records only tools and outcomes used in the project; public share links must be added by the team before form submission.</div>
<h2>1. Tools and roles</h2><table><tr><th>Tool / system</th><th>How it supported the work</th></tr>
<tr><td>Codex CLI</td><td>Repository inspection, backend/API hardening, smoke tests, documentation and submission assembly.</td></tr>
<tr><td>LLM providers in the product</td><td>Optional facilities-copilot explanations with deterministic local fallback when a provider or network is unavailable.</td></tr>
<tr><td>Python / FastAPI / scikit-learn</td><td>Data ingestion, validation, edge classification, demand forecasting, dashboard APIs and CSV predictions.</td></tr>
<tr><td>HTML, CSS, JavaScript, Chart.js</td><td>Interactive dashboard, facility alerts, allocation views and evaluator-facing guide screens.</td></tr></table>
<h2>2. Prompt iteration log</h2>
<table><tr><th>Iteration</th><th>Representative prompt</th><th>Decision / outcome</th></tr>
<tr><td>Schema & constraints</td><td>“Inspect all P2P dataset tables and map their fields to the problem constraints. Identify late data, aliases and unit conflicts.”</td><td>Defined validation, normalization, deduplication and traceable ingestion rules.</td></tr>
<tr><td>Waste classification</td><td>“Compare sensor-only and edge-available feature sets; retain a model that meets the accuracy and latency constraints.”</td><td>Selected compact forest deployment with explicit sensor-quality features and offline inference.</td></tr>
<tr><td>Forecasting</td><td>“Benchmark 6h and 12h demand forecasts on chronological holdout; document accuracy / footprint trade-offs.”</td><td>Selected lightweight forecasting bundle and exposes forecast outputs in the API.</td></tr>
<tr><td>Operational copilot</td><td>“Ground every recommendation in supplied telemetry, event context and operator notes; supply a deterministic fallback.”</td><td>Implemented evidence-led recommendations without making external LLM availability critical.</td></tr></table>
<h2>3. Human contribution and safeguards</h2><ul><li>Defined the edge-first architecture, measurable success criteria and evaluator workflow.</li><li>Specified idempotent reconciliation for delayed gateway transmissions.</li><li>Chose fairness-aware, building-normalized incentive logic rather than raw consumption comparisons.</li><li>Added input schema validation so jury uploads fail clearly rather than silently producing invalid results.</li></ul>
<h2>4. Public chat share links</h2><div class=\"note\"><b>Team action required before upload:</b> add genuine public share links below. No link has been invented in this workbook.</div>
<table><tr><th>Conversation / evidence</th><th>Public share link</th></tr><tr><td>Prompt-to-product ideation and dataset analysis</td><td>TO BE ADDED BY TEAM</td></tr><tr><td>Backend validation and feature iteration</td><td>TO BE ADDED BY TEAM</td></tr><tr><td>UI / demo-video direction</td><td>TO BE ADDED BY TEAM</td></tr></table>
<div class=\"footer\">Campus Chakra · Prompt Workbook · prepared for Srujana 2026</div>"""
    return write("Campus_Chakra_Prompt_Workbook.html", document("Campus Chakra Prompt Workbook", body))


def build_technical() -> Path:
    body = """
<section class=\"page\">""" + header("Technical Report", "System architecture and data handling · Page 1 of 3") + """
<h2>1. System objective</h2><p>Campus Chakra is a campus resource-operations platform for the Prompt for the Planet challenge. It connects waste-event classification, resource telemetry forecasting, facility anomaly workflows and circular allocation views for an eight-building campus dataset.</p>
<div class=\"grid\"><div class=\"card\"><h3>Edge layer</h3><p>Smart-bin sensor payloads and gateway buffers continue locally during connectivity loss.</p></div><div class=\"card\"><h3>Service layer</h3><p>FastAPI validates uploads, runs deterministic models and returns auditable JSON.</p></div><div class=\"card\"><h3>Experience layer</h3><p>Dashboard turns telemetry into alerts, forecasts and allocation actions.</p></div></div>
<h2>2. Architecture and control flow</h2><ol><li><b>Ingest:</b> hourly streams, daily summaries, manual logs and waste events are uploaded or synchronized.</li><li><b>Validate:</b> required columns, known building identifiers, timestamps and numeric measures are checked at the API boundary.</li><li><b>Reconcile:</b> duplicate / delayed events are handled through deterministic identifiers and sequencing.</li><li><b>Infer:</b> compact classifier, forecast bundle and anomaly logic run locally in the backend.</li><li><b>Explain:</b> dashboard and optional copilot present evidence-led actions; deterministic fallback protects core flows.</li></ol>
<h2>3. Data assets</h2><table><tr><th>Data family</th><th>Use in Campus Chakra</th></tr><tr><td>8 building records + 120-day calendar</td><td>Campus context, occupancy/event alignment and building mapping.</td></tr><tr><td>23,192 hourly telemetry rows</td><td>Forecasting, anomaly baselines and dashboard trends.</td></tr><tr><td>415 manual logs</td><td>Alias normalization and operator-grounded incident context.</td></tr><tr><td>6,314 train + 1,601 test waste events</td><td>Model development and required prediction-file generation.</td></tr></table>
<div class=\"footer\">Campus Chakra · Technical Report · 1 / 3</div></section>
<section class=\"page\">""" + header("Technical Report", "Data handling, privacy and reliability · Page 2 of 3") + """
<h2>4. Data handling pipeline</h2><table><tr><th>Stage</th><th>Implementation</th><th>Why it matters</th></tr><tr><td>Schema gate</td><td>API endpoint checks mandatory fields and type-convertible numeric values before modeling.</td><td>Prevents silent corruption from jury or gateway uploads.</td></tr><tr><td>Normalization</td><td>Maps building aliases and consistent units before aggregation.</td><td>Makes formal telemetry and operator-entered logs comparable.</td></tr><tr><td>Time integrity</td><td>Parses timestamps, sorts streams and uses idempotent gateway sequencing.</td><td>Supports delayed / retransmitted field data without double-counting.</td></tr><tr><td>Feature engineering</td><td>Sensor quality flags, temporal features and historic resource baselines are produced at inference.</td><td>Preserves repeatable, edge-compatible model behavior.</td></tr><tr><td>Serving</td><td>Models load from local cache; deterministic logic remains available when optional cloud services fail.</td><td>Maintains a usable evaluator demo under weak connectivity.</td></tr></table>
<h2>5. Security and privacy approach</h2><ul><li>Input validation reduces unsafe parsing and malformed-upload risk.</li><li>Secrets are read from environment configuration; API keys are not embedded in client pages.</li><li>The supplied challenge dataset is handled as a synthetic / competition dataset; production deployment would require institution-approved access controls, retention policy and consent review.</li><li>Recommendations are operational decision support, with facility staff retaining approval authority.</li></ul>
<h2>6. Failure handling</h2><div class=\"callout\"><b>Offline first:</b> classification, forecast and integrity paths do not depend on a live third-party LLM. The copilot can enrich explanations, but core predictions remain deterministic.</div><ul><li>Invalid uploads return readable HTTP validation errors.</li><li>Missing or unavailable optional services return a known fallback status rather than blocking the dashboard.</li><li>Gateway synchronization uses a high-resolution sequence to avoid collisions during rapid retries.</li></ul>
<div class=\"footer\">Campus Chakra · Technical Report · 2 / 3</div></section>
<section class=\"page\">""" + header("Technical Report", "Models, validation and scalability · Page 3 of 3") + """
<h2>7. Models and evaluator workflow</h2><table><tr><th>Capability</th><th>Approach</th><th>Evaluator-facing output</th></tr><tr><td>Waste sorting</td><td>Compact random-forest classifier using physical sensor readings and quality indicators.</td><td>Predicted class plus confidence; test output in <code>waste_events_test_predictions.csv</code>.</td></tr><tr><td>Demand outlook</td><td>Short-horizon feature bundle for electricity and water demand.</td><td>6h / 12h forecast values, direction and risk context.</td></tr><tr><td>Facility alerts</td><td>Rule-based and statistical signals joined with building and event context.</td><td>Prioritized alert cards with suggested next action.</td></tr><tr><td>Circular routing</td><td>Class-aware allocation logic maps material streams to recovery paths.</td><td>Waste allocation / recovery summary for operations teams.</td></tr></table>
<h2>8. Validation performed</h2><ul><li>Dashboard endpoint response check.</li><li>Single-event classifier check and full 1,601-row waste test-file upload check.</li><li>Hourly-stream forecast upload check and manual-log evaluation check.</li><li>Gateway synchronization retry / duplicate behavior check.</li><li>Prediction CSV verified to contain exactly <code>event_id,predicted_class</code> and 1,601 predictions.</li></ul>
<h2>9. Scalability and next steps</h2><p>The service keeps core inference local and stateless per request, allowing buildings to be added primarily through configuration and telemetry onboarding. A production rollout would add authenticated users, encrypted durable storage, monitoring, calibration procedures and a scheduled retraining / model-governance process.</p>
<div class=\"note\"><b>Evaluation boundary:</b> reported functionality is based on the supplied competition dataset and local smoke tests. It should be assessed as a working competition prototype, not as a claim of live campus deployment.</div>
<div class=\"footer\">Campus Chakra · Technical Report · 3 / 3</div></section>"""
    return write("Campus_Chakra_Technical_Report.html", document("Campus Chakra Technical Report", body))


def build_screens() -> Path:
    screenshot = (ASSETS / "campus-chakra-dashboard.png").resolve().as_uri()
    body = header("UI Screenshots Package", "Telemetry dashboard, circular allocation and facility alerts") + f"""
<div class=\"callout\"><b>Submission note.</b> The live prototype opens with a logo reveal, then exposes the Campus Chakra operational experience. This document groups relevant screens and explicit workflow annotations into a single PDF, as required.</div>
<h2>1. Campus Chakra entry and telemetry workspace</h2><img class=\"shot\" src=\"{screenshot}\"><div class=\"caption\">Figure 1 — Live local Campus Chakra capture. The opening state uses the Campus Chakra identity and provides entry to the operations dashboard.</div>
<h2>2. Telemetry dashboard</h2><div class=\"mock\"><div class=\"mock-head\">CAMPUS CHAKRA · RESOURCE TELEMETRY</div><div class=\"mock-body\"><div class=\"grid\"><div class=\"card\"><div class=\"kpi\">23,192</div><b>Hourly records</b><p>Time-series monitoring across campus buildings.</p></div><div class=\"card\"><div class=\"kpi\">6h / 12h</div><b>Demand outlook</b><p>Operational horizon for electricity and water planning.</p></div><div class=\"card\"><div class=\"kpi\">8</div><b>Facilities</b><p>Building-aware resource context and comparisons.</p></div></div></div></div><div class=\"caption\">Figure 2 — Telemetry dashboard workflow: ingest validated streams, compare building baselines and surface short-horizon forecasts.</div>
<h2>3. Circular waste allocation</h2><div class=\"mock\"><div class=\"mock-head\">CIRCULAR ROUTING · SMART-BIN CLASSIFICATION</div><div class=\"mock-body\"><table><tr><th>Detected material</th><th>Confidence-led route</th><th>Operations action</th></tr><tr><td>Food organic</td><td>Composting / biodigester</td><td>Assign collection slot</td></tr><tr><td>Paper, plastic, glass, metal</td><td>Segregated recycler stream</td><td>Track diversion and contamination</td></tr><tr><td>E-waste</td><td>Certified recovery partner</td><td>Flag controlled handling</td></tr></table></div></div><div class=\"caption\">Figure 3 — Circular allocation workflow: the uploaded waste-event sensor fields produce a predicted class, then route materials toward the appropriate recovery path.</div>
<h2>4. Facility alerts and action loop</h2><div class=\"mock\"><div class=\"mock-head\">FACILITY ALERTS · EVIDENCE-LED RESPONSE</div><div class=\"mock-body\"><table><tr><th>Signal</th><th>Evidence</th><th>Action</th></tr><tr><td>Unusual water demand</td><td>Building baseline + time window + manual-log context</td><td>Inspect leak / fixture and close the alert with outcome.</td></tr><tr><td>Energy spike</td><td>Forecast deviation + calendar / occupancy context</td><td>Review HVAC, inverter or scheduled load.</td></tr><tr><td>Waste contamination</td><td>Smart-bin prediction and low-confidence sensor flag</td><td>Trigger bin check or collection-team instruction.</td></tr></table></div></div><div class=\"caption\">Figure 4 — Facility alert workflow: a signal is tied to evidence and a specific operator action rather than a generic chart warning.</div>
<div class=\"footer\">Campus Chakra · UI Screenshots Package · single PDF submission</div>"""
    return write("Campus_Chakra_UI_Screenshots.html", document("Campus Chakra UI Screenshots", body))


def build_overview() -> Path:
    body = header("Project Overview", "From campus resource complexity to an evaluator-ready prototype") + """
<h2>Initial idea</h2><p>Campuses need a single operational view of electricity, water and waste, but real facilities data is noisy, delayed and distributed across sensor feeds and manual notes. Campus Chakra was conceived as an edge-native circular-resource grid that turns these disconnected signals into timely, understandable actions.</p>
<h2>Development process</h2><ol><li>Read the competition problem statement and all provided data files.</li><li>Mapped data constraints to four workflows: ingestion integrity, waste classification, short-horizon demand outlook and facility action.</li><li>Implemented backend endpoints with explicit upload validation and deterministic fallback behavior.</li><li>Built the Campus Chakra dashboard experience, guide flow and brand entrance.</li><li>Ran local smoke tests with the supplied competition files and produced the required test predictions.</li></ol>
<h2>Implemented features</h2><div class=\"grid\"><div class=\"card\"><h3>Reliable data intake</h3><p>Checks schemas, timestamps, numeric telemetry and known facilities before analysis.</p></div><div class=\"card\"><h3>Smart-bin inference</h3><p>Predicts a waste stream from sensor fields and exports competition-ready predictions.</p></div><div class=\"card\"><h3>Forecast and alerts</h3><p>Transforms past demand into 6h / 12h planning signals and facility follow-ups.</p></div></div>
<h2>Tools used</h2><table><tr><th>Layer</th><th>Tools</th></tr><tr><td>Backend and data</td><td>Python, FastAPI, pandas, scikit-learn</td></tr><tr><td>Frontend</td><td>HTML, CSS, JavaScript, Chart.js, GSAP, Lenis</td></tr><tr><td>AI-assisted development</td><td>Codex CLI and product-integrated LLM providers with deterministic fallbacks</td></tr><tr><td>Delivery validation</td><td>Local endpoint checks, CSV verification, PDF generation and UI capture</td></tr></table>
<h2>Final outcome</h2><div class=\"callout\"><b>Campus Chakra is a working competition prototype:</b> jurors can upload the supplied-format data, receive classification and forecast outputs, inspect facility workflows and review a clean submission package. The design intentionally keeps essential intelligence available locally so the demo remains functional even when optional external AI services are unavailable.</div>
<h2>What makes it useful</h2><ul><li>Combines resource telemetry and waste operations instead of treating them as isolated dashboards.</li><li>Prioritizes explainable action: each alert has a relevant evidence path and next step.</li><li>Maintains data integrity through validation and idempotent synchronization.</li><li>Creates a direct bridge from sensor classification to circular-resource allocation.</li></ul>
<div class=\"footer\">Campus Chakra · Project Overview · prepared for Srujana 2026</div>"""
    return write("Campus_Chakra_Project_Overview.html", document("Campus Chakra Project Overview", body))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    files = [
        (build_workbook(), "Campus_Chakra_Prompt_Workbook.pdf"),
        (build_technical(), "Campus_Chakra_Technical_Report.pdf"),
        (build_screens(), "Campus_Chakra_UI_Screenshots.pdf"),
        (build_overview(), "Campus_Chakra_Project_Overview.pdf"),
    ]
    for html_file, pdf_name in files:
        render(html_file, pdf_name)
    shutil.copyfile(ROOT / "waste_events_test_predictions.csv", OUT / "waste_events_test_predictions.csv")
    print("Submission files created in", OUT)


if __name__ == "__main__":
    main()
