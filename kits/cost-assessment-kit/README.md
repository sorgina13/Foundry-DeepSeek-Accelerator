# Cost Assessment Kit

**Status:** Current release

Answers: What does it save?

[Back to the accelerator roadmap](../../README.md#roadmap).


Edit the endpoint and deployment names in `benchmark.py`.

## Install with uv

From PowerShell in this directory:

```powershell
uv venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

The script uses `DefaultAzureCredential`. Sign in with Azure CLI before running it,
or configure another supported Azure credential source:

```powershell
az login
```

## Run

```powershell
uv run --python .venv\Scripts\python.exe benchmark.py
```

The benchmark reads `prompts.jsonl` and writes results to `results.csv`.

## Foundry cloud evaluation

`foundry_eval_dataset.jsonl` contains 100 balanced tasks that can be used for
Foundry model evaluation and prompt optimization. Validate it without Azure access:

```powershell
uv run --python .venv\Scripts\python.exe prepare_foundry_evaluation.py --validate-only
```

Set the Foundry project endpoint and a fixed judge deployment. The endpoint must
include `/api/projects/<project-name>`; it is not the `/openai/v1` inference endpoint.

```powershell
$env:AZURE_AI_PROJECT_ENDPOINT = "https://<account>.services.ai.azure.com/api/projects/<project>"
$env:AZURE_AI_JUDGE_DEPLOYMENT = "<judge-deployment>"
```

Create the versioned dataset, custom evaluator, and evaluation definition without
starting model calls:

```powershell
uv run --python .venv\Scripts\python.exe prepare_foundry_evaluation.py --prepare-only
```

Run the same evaluation against all three configured deployments:

```powershell
uv run --python .venv\Scripts\python.exe prepare_foundry_evaluation.py
```

Use `--profile full` to add the five safety evaluators. The default `core` profile
controls judge cost while retaining coherence, relevance, completeness, F1, and
per-row behavioral adherence. Run metadata and row-level output are written to
`eval_results/`.

See `FOUNDRY_PORTAL_GUIDE.md` for the equivalent portal workflow and recommended
comparison and prompt-optimization settings.