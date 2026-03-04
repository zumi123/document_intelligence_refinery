# Push to GitHub and run in Colab

## 1. Create a new repo on GitHub

1. Go to [github.com/new](https://github.com/new).
2. Repository name: `document_intelligence` (or any name).
3. Choose **Public**, do **not** add a README (you already have one).
4. Create the repository.

## 2. Push from your local machine

From your project folder (where you have the code but can't run it):

```bash
cd "/home/zumi/Documents/10 Academy Training/Week 3/document_intelligence"

# Initialize git if not already
git init

# Add everything (respects .gitignore: no PDFs, no .refinery artifacts, no venv)
git add .
git commit -m "Interim: models, triage, strategies, extractor, tests, Colab notebook"

# Add your GitHub repo as remote (replace YOUR_USERNAME and REPO_NAME with yours)
git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git

# Push (main or master)
git branch -M main
git push -u origin main
```

If the repo already had a remote:

```bash
git remote set-url origin https://github.com/YOUR_USERNAME/REPO_NAME.git
git push -u origin main
```

## 3. Data (PDFs) not in the repo

`.gitignore` excludes `data/*.pdf` so the repo stays small. To run in Colab you need the PDFs there:

**Option A — Upload in Colab**

1. On your machine, zip the `data/` folder (with all PDFs inside):
   ```bash
   cd "/home/zumi/Documents/10 Academy Training/Week 3/document_intelligence"
   zip -r data.zip data/
   ```
2. In Colab, when the notebook asks for data, upload `data.zip`.
3. The notebook will unzip it into the repo’s `data/` folder.

**Option B — Push PDFs with Git LFS (optional)**

If you want the PDFs in the repo:

```bash
git lfs install
git lfs track "data/*.pdf"
git add .gitattributes
git add data/*.pdf
git commit -m "Add data PDFs (LFS)"
git push
```

Then in Colab you don’t need to upload a zip; clone will get the files (and LFS will pull them).

## 4. Run in Google Colab

1. Open [colab.research.google.com](https://colab.research.google.com).
2. **File → Open notebook → GitHub** and enter your repo URL, e.g.  
   `https://github.com/YOUR_USERNAME/document_intelligence`  
   and open **`run_refinery_interim.ipynb`**.
3. In the first code cell, set `REPO_URL` to your repo URL (same as above).
4. Run all cells. When asked, upload your `data.zip` (if you didn’t push PDFs).
5. At the end, download **`refinery_artifacts.zip`** (contains `.refinery/profiles/` and `extraction_ledger.jsonl`).

See **README_COLAB.md** for more detail.
