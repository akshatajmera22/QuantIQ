# QuantIQ Step 1 - Dynamic Dataset Layer

## What changed

- The original `database.db` remains available as the default dataset.
- Excel uploads create a separate SQLite database under `data/datasets/`.
- Multiple Excel files can be uploaded in one batch.
- Every Excel sheet becomes a queryable table.
- CSV uploads are supported.
- The uploaded dataset becomes the active dataset automatically.
- `/query` now resolves schema, values, SQL validation, and execution from the active dataset.
- `/datasets` shows available datasets.
- `/datasets/select` switches the active dataset.
- `/upload` ingests Excel/CSV files.
- The planner no longer assumes the data is automobiles.
- Planner uses the Ollama CLI with CPU execution to avoid the GTX 1650 CUDA crash.

## Install

From the project root:

```powershell
pip install openpyxl python-multipart
```

Your existing FastAPI/pandas/uvicorn packages can remain.

## Run backend

```powershell
$env:OLLAMA_LLM_LIBRARY="cpu_avx2"
uvicorn api:app --reload
```

## Run frontend

In another terminal:

```powershell
cd frontend
npm install
npm install lucide-react
npm install tailwindcss @tailwindcss/vite
npm run dev
```

Then upload an Excel file from QuantIQ. The upload is not just a UI state anymore: it creates an isolated SQLite dataset and makes it active, so subsequent `/query` calls use that dataset.

## Important

This step intentionally supports Excel/CSV first. MySQL and SQL Server connection support will be added after file-based datasets are verified.
