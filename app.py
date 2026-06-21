import streamlit as st
import os
import time
import tempfile
from dotenv import load_dotenv
from agent import run_agent
from pdf_report import generate_pdf

load_dotenv()

st.set_page_config(
    page_title="Business Analytics Agent",
    page_icon="📊",
    layout="wide"
)

st.markdown("""
<style>
    .block-container { padding-top: 2.5rem; max-width: 960px; }

    h1 {
        font-size: 1.9rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.3px;
    }

    .subtitle {
        color: #8b949e;
        font-size: 0.95rem;
        margin-top: -8px;
        margin-bottom: 2rem;
        line-height: 1.6;
    }

    .model-badge {
        display: inline-block;
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 4px;
        padding: 1px 7px;
        font-size: 0.78rem;
        color: #8b949e;
        font-family: 'Courier New', monospace;
        vertical-align: middle;
    }

    .section-label {
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1.8px;
        color: #8b949e;
        margin-bottom: 10px;
        margin-top: 24px;
    }

    .summary-box {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 18px 22px;
        font-size: 0.95rem;
        line-height: 1.7;
        color: #e6edf3;
    }

    .finding-item {
        border-left: 3px solid #388bfd;
        padding: 10px 14px;
        margin: 7px 0;
        background: #161b22;
        border-radius: 0 6px 6px 0;
        font-size: 0.88rem;
        line-height: 1.55;
        color: #e6edf3;
    }

    .rec-item {
        border-left: 3px solid #3fb950;
        padding: 10px 14px;
        margin: 7px 0;
        background: #161b22;
        border-radius: 0 6px 6px 0;
        font-size: 0.88rem;
        line-height: 1.55;
        color: #e6edf3;
    }

    .status-line {
        font-family: 'Courier New', monospace;
        font-size: 0.8rem;
        color: #8b949e;
        padding: 2px 0;
    }
</style>
""", unsafe_allow_html=True)

# Session state
for key, default in [
    ("report", None), ("charts", []), ("csv_path", None), ("file_key", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

st.title("Business Analytics Agent")
st.markdown(
    "<p class='subtitle'>Upload sales or transaction data to get an AI-powered executive report "
    "with trend analysis, customer segments, anomalies and actionable recommendations.</p>",
    unsafe_allow_html=True,
)
st.markdown("<span class='model-badge'>Llama 3.3 70B · Groq</span>", unsafe_allow_html=True)

groq_api_key = st.text_input(
    "Please enter your Groq API Key to run the analysis",
    type="password",
    placeholder="gsk_...",
    help="Free at console.groq.com — no credit card required",
)

uploaded_file = st.file_uploader("Upload CSV", type=["csv"], label_visibility="collapsed")

if uploaded_file:
    file_key = f"{uploaded_file.name}_{uploaded_file.size}"

    # New file: save to temp and reset state
    if file_key != st.session_state.file_key:
        if st.session_state.csv_path and os.path.exists(st.session_state.csv_path):
            os.unlink(st.session_state.csv_path)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp.write(uploaded_file.getvalue())
            st.session_state.csv_path = tmp.name
        st.session_state.file_key = file_key
        st.session_state.report = None
        st.session_state.charts = []

    st.markdown(f"<p style='color:#8b949e; font-size:0.85rem;'>📄 {uploaded_file.name}</p>", unsafe_allow_html=True)

    if not groq_api_key:
        st.warning("Enter your Groq API key above to run the analysis.")

    _, col_btn, _ = st.columns([3, 2, 3])
    with col_btn:
        run_btn = st.button("Run Analysis", type="primary", width='stretch', disabled=not groq_api_key)

    if run_btn:
        log_container = st.empty()
        logs = []
        start_time = time.time()
        step = [0]

        step_labels = {
            "inspect_csv": "Inspecting data structure",
            "finish_report": "Compiling executive report",
        }

        def update_status(fn_name, fn_args):
            step[0] += 1
            elapsed = int(time.time() - start_time)
            if fn_name == "run_python":
                label = fn_args.get("description", "Running analysis")
            else:
                label = step_labels.get(fn_name, fn_name)
            logs.append((step[0], label, elapsed))
            lines = "".join(
                f"<div class='status-line'>Step {s} &nbsp;·&nbsp; {l} &nbsp;<span style='color:#444d56'>{e}s</span></div>"
                for s, l, e in logs
            )
            log_container.markdown(lines, unsafe_allow_html=True)

        try:
            with st.spinner("Agent is working..."):
                report, charts = run_agent(st.session_state.csv_path, api_key=groq_api_key, status_callback=update_status)
        except Exception as e:
            log_container.empty()
            st.error(f"Agent error: {e}")
            st.stop()

        elapsed_total = int(time.time() - start_time)
        log_container.empty()

        if report:
            st.session_state.report = report
            st.session_state.charts = charts
            st.session_state.elapsed = elapsed_total
        else:
            st.error("The agent did not produce a report. Check your API key and try again.")

    # Display report from session state
    if st.session_state.report:
        report = st.session_state.report
        charts = st.session_state.charts

        st.markdown("---")
        st.markdown(
            f"<p style='color:#8b949e; font-size:0.8rem; margin-bottom:1.5rem;'>"
            f"Analysis completed · {len(charts)} charts · Llama 3.3 70B via Groq</p>",
            unsafe_allow_html=True,
        )

        pdf_bytes = generate_pdf(report, charts)
        st.download_button(
            label="Download PDF report",
            data=pdf_bytes,
            file_name="analytics_report.pdf",
            mime="application/pdf",
        )

        st.markdown("<div class='section-label'>Executive Summary</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='summary-box'>{report['summary']}</div>", unsafe_allow_html=True)

        col_f, col_r = st.columns(2)

        with col_f:
            st.markdown("<div class='section-label'>Key Findings</div>", unsafe_allow_html=True)
            for finding in report["findings"]:
                st.markdown(f"<div class='finding-item'>{finding}</div>", unsafe_allow_html=True)

        with col_r:
            st.markdown("<div class='section-label'>Recommendations</div>", unsafe_allow_html=True)
            for rec in report["recommendations"]:
                st.markdown(f"<div class='rec-item'>{rec}</div>", unsafe_allow_html=True)

        if charts:
            st.markdown("---")
            st.markdown("<div class='section-label'>Analysis Charts</div>", unsafe_allow_html=True)
            for chart_path in sorted(charts):
                st.image(chart_path, width='stretch')

