# Run the Refinery in Google Colab

After pushing this repo to GitHub, run everything in Colab as follows.

## 1. Open Colab and clone your repo

1. Go to [Google Colab](https://colab.research.google.com).
2. **File → Open notebook → GitHub** and paste your repo URL, e.g.  
   `https://github.com/YOUR_USERNAME/document_intelligence`
3. Or: **File → Upload** and upload `run_refinery_interim.ipynb` from this repo.

## 2. Use the notebook

Open **`run_refinery_interim.ipynb`** in Colab. It will:

- Clone the repo (or use the uploaded notebook’s folder).
- Install dependencies (`pip install -e .` and optional `docling`, `pymupdf`).
- Ask you to **upload your `data.zip`** (or the `data/` folder with PDFs) to `/content/document_intelligence/data/`.
- Run Phase 0 scripts (character density, optional Docling).
- Run **`scripts/run_interim_artifacts.py`** to generate 12 profiles and `extraction_ledger.jsonl`.
- Run tests.

## 3. Get artifacts back

- **.refinery/profiles/** and **.refinery/extraction_ledger.jsonl** are created under the repo folder in Colab.
- Download the whole folder (e.g. **Files** panel → right‑click `document_intelligence` → Download), or zip and download:
  ```python
  !cd /content/document_intelligence && zip -r refinery_artifacts.zip .refinery
  ```
  Then download `refinery_artifacts.zip` from the Colab file browser.

## 4. If you didn’t push the PDFs (they’re in .gitignore)

- Zip your local `data/` (with the PDFs) on your machine.
- In Colab, run the notebook; when it asks for data, **upload** that zip and run the cell that unzips it into `data/`.
