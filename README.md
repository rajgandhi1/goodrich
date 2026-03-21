# Gasket Quote Processor — MVP

Automates gasket enquiry processing for **soft cut gaskets** (ASME & EN/PN standards).
Converts customer enquiries (email text or Excel) into the internal GGPL quote format.

## Quick Start

### 1. Install dependencies
```bash
conda activate fl
pip install -r requirements.txt
```

### 2. Run the app
```bash
conda activate fl
streamlit run app.py
```

### 3. (Optional) Add Groq API key for AI extraction
Get a free key at [console.groq.com](https://console.groq.com) — no credit card needed.
Enter it in the sidebar when the app is running, or add to `.streamlit/secrets.toml`:
```toml
GROQ_API_KEY = "your_key_here"
```

## Deploy to Streamlit Community Cloud (free)
1. Push this repo to a public GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Select the repo and set entry point to `app.py`
4. Add `GROQ_API_KEY` in the Secrets settings

## How it works
1. **Paste** email text or **upload** Excel file
2. System extracts gasket specs and maps to GGPL format
3. Review table shows:
   - ✅ **Ready** — all fields confirmed
   - 🟡 **Check** — defaults were applied (verify before sending)
   - 🔴 **Action needed** — critical info missing, customer must clarify
4. Draft RFI email auto-generated for missing items
5. **Download** quote Excel with all items colour-coded

## Reference Data
Reference files are in `/reference/`:
- `SOFT CUT ASME STANDARD DIMENSION & SOFT CUT MOC.xlsx` — dimension lookup tables
- `SOFTCUT DESCRIPTION.xlsx` — 357 customer→GGPL description mapping examples

## Running Tests
```bash
conda activate fl
python tests/test_pipeline.py
```
