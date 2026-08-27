# Cost Assessment Kit

**Status:** Current release

Answers: What does it save?

[Back to the accelerator roadmap](../../README.md#roadmap).


Edit the endpoint and deployment names in `benchmark.py` for the original
command-line benchmark, or use the notebook workflow below for the full cost,
cache, latency, output-length, and semantic-consistency analysis.

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

## Run the analysis notebook

Open `model_cost_and_similarity_analysis.ipynb` with the `.venv` kernel and run
all cells. Its default configuration is safe and offline:

```python
RUN_LIVE = False
CREATE_FOUNDRY_ASSETS = False
START_FOUNDRY_EVALUATION_RUNS = False
```

This mode creates 900 deterministic synthetic observations: 100 prompts, three
models, one cold run, and two warm repetitions. It exercises the complete
analysis and export path without model, embedding, evaluator, or asset-creation
calls. Synthetic token usage, cache hits, latency, responses, and similarity are
illustrative and must not be presented as service measurements.

For a live generation and embedding experiment, set `RUN_LIVE = True` and
configure these environment variables before running the notebook:

```powershell
$env:AZURE_AI_PROJECT_ENDPOINT = "https://<account>.services.ai.azure.com/api/projects/<project>"
$env:AZURE_OPENAI_ENDPOINT = "https://<account>.services.ai.azure.com/openai/v1"
$env:AZURE_OPENAI_EMBEDDING_DEPLOYMENT = "<embedding-deployment>"
$env:AZURE_AI_JUDGE_DEPLOYMENT = "<judge-deployment>"
```

`CREATE_FOUNDRY_ASSETS` separately controls dataset, evaluator, and evaluation
definition creation. `START_FOUNDRY_EVALUATION_RUNS` starts additional paid
Foundry evaluation runs and only has an effect when asset creation is enabled.

The notebook writes reproducible outputs under `analysis_results/`, including
detailed and aggregate CSV files, similarity pairs and statistics, cached
vectors, a decision chart, and `experiment_manifest.json`. The manifest records
dataset and pricing hashes, package versions, execution mode, and analysis
limitations.

Cross-model response similarity is reported separately for DeepSeek versus
GPT-4.1 mini, DeepSeek versus GPT-5.4, and GPT-4.1 mini versus GPT-5.4. These
comparisons match the same prompt, phase, and repetition before averaging by
prompt, so cold and warm run conditions are not mixed. See
`model_pair_similarity_summary.csv`, `matched_cross_model_pairs.csv`, and
`model_pair_similarity.png` for the scorecard, row-level evidence, and chart.
The companion `model_pair_correlation_by_run.png` line chart shows Pearson
correlation across embedding dimensions for each matched cold or warm run.
Cosine similarity is the primary semantic-agreement measure; correlation is a
secondary centered-shape diagnostic. Neither metric establishes correctness,
safety, or factual quality.

## Pricing assumptions

Token costs use published USD global pay-as-you-go prices retrieved August 27,
2026. The benchmark records the applicable input and output prices alongside
each result so historical runs retain their pricing assumptions.

| Model | Input / 1M tokens | Cached input / 1M tokens | Output / 1M tokens |
| --- | ---: | ---: | ---: |
| DeepSeek-V4-Flash | $0.19 | $0.028 | $0.51 |
| gpt-5.4 (under 272K context) | $2.50 | $0.25 | $15.00 |
| gpt-4.1-mini | $0.40 | $0.10 | $1.60 |

The command-line benchmark calculates input and output costs independently as
`tokens * price / 1,000,000`, then sums them for `total_cost_usd`. The notebook
additionally separates provider-reported cached and uncached input tokens and
applies the corresponding rates from `model_pricing.json`. Batch, data-zone,
regional, long-context, provisioned-throughput, and negotiated pricing changes
are not modeled. Confirm the applicable Azure meter before external reporting.

Embedding usage and cost are separate from generation. Set
`EMBEDDING_PRICE_PER_1M_USD` when a reviewed embedding price is available;
otherwise the notebook reports embedding tokens without inventing a charge.

Sources: [DeepSeek model pricing](https://aka.ms/DeepSeekModelPricing) and
[Azure OpenAI pricing](https://aka.ms/AzureOAIpricing).

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