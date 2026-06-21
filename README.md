# Business Analytics Agent

An AI-powered agent that analyzes sales and transaction data and generates an executive report with trend analysis, customer segments, anomalies and actionable recommendations.

**[Live demo](#)** ← replace after deploying

---

## What it does

Most analytics tools require you to know what questions to ask before you start. This agent flips that: you upload a CSV and it figures out what's worth analyzing on its own.

The agent inspects the data structure, decides which analyses make sense for that specific dataset, writes and executes Python code to run them, and compiles the results into a plain-language executive report. The output is designed for non-technical stakeholders — specific numbers, business context, and actionable recommendations.

It is optimized for sales and transaction datasets: e-commerce orders, retail point-of-sale, sales pipelines — anything with customers, products, quantities, prices, and dates.

---

## How it works

```
User uploads CSV
    ↓ inspect_csv tool
Schema, dtypes, nulls, sample rows, numeric summary
    ↓ LLM plans analyses based on what it finds
run_python tool (analysis 1: revenue trend)
run_python tool (analysis 2: top customers)
run_python tool (analysis 3: geographic breakdown)
    ... (agent decides how many)
    ↓ finish_report tool
Executive summary + key findings + recommendations
    ↓ Streamlit UI
Interactive report + charts + optional PDF export
```

This is a real agentic loop — the model calls tools, reads the outputs, and decides what to do next. It is not a fixed pipeline.

---

## Stack

| Layer | Technology |
|---|---|
| LLM | Llama 3.3 70B via [Groq](https://groq.com/) |
| Agent loop | Groq function calling (no framework) |
| UI | [Streamlit](https://streamlit.io/) |
| Analysis | pandas + matplotlib |
| PDF export | fpdf2 |

---

## Key design decisions

**Function calling over frameworks:** The agent loop is ~50 lines of plain Python. No LangChain, no LangGraph. Using the model's native tool use keeps the reasoning in the model and the plumbing transparent — easier to debug, easier to explain.

**Dynamic code execution:** The agent writes and runs Python for each analysis rather than calling pre-built functions. This means it can handle columns it has never seen before and adapt the analysis to the actual data shape.

**Path injection:** On Windows, the LLM double-escapes backslashes when it serializes file paths to JSON. The agent loop overwrites the path argument before calling any tool, so the model never controls the actual file path.

**Context truncation:** Tool outputs are capped at 1500 characters before being added to the message history. This keeps the conversation within token limits across multiple analysis steps without losing the signal the model needs.

---

## Project structure

```
├── app.py              # Streamlit UI
├── agent.py            # Agent loop and tool definitions
├── tools.py            # Tool implementations (inspect_csv, run_python, finish_report)
├── prompts.py          # System prompt
├── pdf_report.py       # PDF export with fpdf2
├── .streamlit/
│   └── config.toml     # Dark theme
└── data/               # Local CSVs, excluded from git
```

---

## Local setup

```bash
git clone https://github.com/matigorenberg/business-analytics-agent
cd business-analytics-agent

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

pip install -r requirements.txt

cp .env.example .env
# Add your GROQ_API_KEY — free tier at console.groq.com

streamlit run app.py
```

---

## Demo dataset

The demo uses the [Online Retail dataset](https://archive.ics.uci.edu/dataset/352/online+retail) from UCI — real UK e-commerce transactions, ~500k rows. Download the Excel file and convert:

```python
import pandas as pd
pd.read_excel("data/Online Retail.xlsx").to_csv("data/online_retail.csv", index=False)
```

The agent works with any business CSV — the dataset is only needed for the demo.

---

## Deployment

Deploy for free on [Streamlit Community Cloud](https://streamlit.io/cloud):

1. Push this repo to GitHub
2. Go to share.streamlit.io → New app → select the repo
3. Add `GROQ_API_KEY` under **Settings → Secrets**
4. Deploy
