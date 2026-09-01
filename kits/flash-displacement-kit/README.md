# Flash Displacement Kit

**Status:** Notebook demonstrator

The Flash Displacement Kit demonstrates how to turn a small, representative prompt
set into a displacement scorecard for an existing Microsoft Foundry model deployment.

[Back to the accelerator roadmap](../../README.md#roadmap).

## What the notebook demonstrates

The notebook runs each test case three times and records:

| Measure | How the demonstrator calculates it |
|---|---|
| Quality | Fraction of expected keywords found in the response |
| Latency | Mean request duration compared with a target |
| Tokens | Prompt, completion, and total tokens reported by the API |
| Estimated cost | Token usage multiplied by customer-supplied rates |
| Stability | Latency variation across repeated runs |
| Decision | Weighted score plus a minimum quality threshold |

The keyword check is deliberately simple and visible. Replace it with task-specific
checks or an evaluator before using the result for a production decision.

## Safe default

The notebook starts with `RUN_LIVE_EVALUATION = False`. In this mode it uses clearly
labelled illustrative observations, requires no credentials, makes no network calls,
and incurs no model charges.

Live mode uses the Foundry project endpoint and deployment name from `.env`. It sends
three requests per test case and may incur Azure charges.

## Run the demonstrator

### 1. Configure the deployment

Create `.env` from `.env.example` and set:

```dotenv
PROJECT_ENDPOINT="https://<resource>.services.ai.azure.com/api/projects/<project>"
MODEL_DEPLOYMENT_NAME="<your-model-deployment>"
```

To use an `.env` elsewhere, set `FDKIT_ENV_FILE` to its path before starting the
notebook.

Cost is optional. For a live cost score, add current rates from the Azure pricing
calculator:

```dotenv
INPUT_PRICE_PER_MILLION_USD="0"
OUTPUT_PRICE_PER_MILLION_USD="0"
```

The notebook does not guess prices. In live mode, cost is excluded from the weighted
score when both rates remain zero.

### 2. Prepare the Python environment

From this directory:

```bash
python -m pip install \
  --index-url https://packagefeedproxy.microsoft.io/pypi/simple \
  -r requirements.txt
```

### 3. Run the notebook

Open `notebooks/displacement-scorecard-demo.ipynb` and run all cells.

For a no-cost walkthrough, leave `RUN_LIVE_EVALUATION = False`. To evaluate the
configured deployment, change it to `True` in the first code cell and run all cells
again.

## Score calculation

The default weights are:

| Category | Weight |
|---|---:|
| Quality | 60% |
| Latency | 20% |
| Cost | 10% |
| Stability | 10% |

Each category score is between 0 and 1. The overall score is the weighted average of
available categories. A row passes when:

- average quality is at least 80%; and
- overall displacement score is at least 80%.

Edit `TEST_CASES`, `WEIGHTS`, and `THRESHOLDS` in the notebook to reflect the customer
workload. The supplied three cases are examples only.

## Outputs

Running the export cell creates:

- `reports/displacement-scorecard.csv` with the aggregate decision rows;
- `results/evaluation-responses.json` with every repeated-run observation.

`results/` and `.env` are excluded from source control.

## Repository layout

```text
flash-displacement-kit/
├── .env.example
├── notebooks/
│   └── displacement-scorecard-demo.ipynb
├── reports/
├── results/
├── requirements.txt
├── config/               # forward-looking evaluation configuration
├── datasets/             # templates and ignored customer data
├── infrastructure/       # no-op infrastructure scaffold
└── src/                  # package scaffold for future automation
```

The notebook uses an existing Foundry project and deployment. It does not provision,
modify, or deploy Azure resources.

## Before relying on a score

- Replace the illustrative prompts with representative customer cases.
- Replace keyword matching when the task needs schema, numeric, semantic, or human
  evaluation.
- Validate current model pricing against the Azure pricing calculator and the
  customer's commercial agreement.
- Compare the candidate with an incumbent model before making a displacement decision.
- Confirm model availability, release status, data handling, and Responsible AI
  requirements for the target environment.