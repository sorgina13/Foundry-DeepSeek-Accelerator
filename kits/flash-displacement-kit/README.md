# Flash Displacement Kit

**Status:** Available

The Flash Displacement Kit evaluates DeepSeek V4 Flash on Microsoft Foundry against
your own workloads and produces a routing decision: which traffic moves, which stays,
and what the move is worth.

[Back to the accelerator roadmap](../../README.md#roadmap).

---

## What this kit does for you

If you run high-volume AI workloads, some of your traffic almost certainly does not
need a frontier model. The hard part is knowing which parts — and proving it before
you change anything in production.

The Flash Displacement Kit answers three questions on your own workloads:

| Your question | What you get back |
|---|---|
| Which of my workloads can DeepSeek V4 Flash handle without dropping below my quality bar? | A displacement scorecard with a **move / hold / investigate** verdict per workload segment |
| What would that actually save at my production volumes? | A cost model based on **cost per completed task**, not per-token rate cards |
| Is the `DeepSeek-V4-Flash-0731` preview snapshot safe for me to adopt? | A regression assessment against the generally available Flash release |

You end up with a routing decision: which traffic moves, which stays, and what the
move is worth.

---

## Which DeepSeek model this kit evaluates, and why

DeepSeek V4 on Foundry is a two-tier family. Choosing the wrong tier is the most
common reason these evaluations produce a misleading result.

| | **DeepSeek V4 Flash** | **DeepSeek V4 Pro** |
|---|---|---|
| Positioned for | Low latency, high throughput, cost-efficient reasoning and coding | Frontier reasoning, complex coding, long-horizon workflows |
| Typical workloads | Chat and conversational experiences, high-volume content generation, classification, summarisation, extraction, real-time assistants | Multi-step reasoning and analysis, complex debugging, long-document synthesis, agentic planning |
| Role in your portfolio | Your volume tier | Your frontier tier |

**This kit evaluates Flash.** It is designed to test whether your volume traffic can
move down a tier — not whether Flash can replace a frontier model on your hardest
tasks. It cannot, and the kit does not test as though it can.

If your question is about complex reasoning or long-context analytical work, see the
[Pro Reasoning Kit on the accelerator roadmap](../../README.md#roadmap).

### `DeepSeek-V4-Flash-0731` specifics

| Attribute | Value |
|---|---|
| Model type | Chat completion, with reasoning content |
| Release status | **Preview** |
| Input context | Text, up to 1,000,000 tokens |
| Output | Text, up to 384,000 tokens |
| Languages | English, Chinese |
| Tool calling | **Not supported** |
| Response formats | Text, JSON |
| Hosting and billing | Foundry Model sold by Azure — hosted and operated by Azure, billed through your Azure subscription |

`-0731` is a dated snapshot of Flash and is currently in preview, sitting alongside the
generally available `DeepSeek-V4-Flash`. Preview releases carry no service-level
agreement and are not recommended for production workloads.

The kit therefore treats **generally available Flash as your production target**, and
`-0731` as a candidate you are testing for regression before adopting. You get both
results and decide.

---

## What this kit will not tell you

Stated plainly so you can scope your own evaluation correctly.

- **Anything about tool calling or agents.** The Azure-direct DeepSeek V4 family does
  not support tool calling. If your workload depends on function calling, this kit is
  not the right test.
- **Whether Flash matches your frontier model overall.** It tests specific workload
  segments against your specific quality thresholds. It does not produce a general
  capability ranking.
- **Provisioned throughput economics.** This kit covers standard pay-per-token
  deployment only. DeepSeek carries a minimum provisioned-throughput commitment, which
  is a separate exercise once you know how much traffic is actually moving.
- **Third-party hosted variants.** A separately hosted DeepSeek V4 Flash offering
  exists in the catalog under different commercial terms. Mixing the two in one cost
  model produces numbers you cannot defend, so this kit covers the Azure-direct model
  only.
- **Availability everywhere.** DeepSeek models are available in global Foundry regions.
  Confirm availability and quota in your target region before you begin.

---

## How it works

The kit deploys three models side by side in a single Foundry project and runs your
evaluation set against all three.

```
                    ┌──────────────────────────────┐
                    │   Your evaluation dataset    │
                    │   segmented by workload type │
                    └───────────────┬──────────────┘
                                    │
                  ┌─────────────────┼─────────────────┐
                  ▼                 ▼                 ▼
        ┌──────────────┐  ┌──────────────────┐  ┌──────────────┐
        │  Flash (GA)  │  │  Flash-0731      │  │  Your current│
        │              │  │  (preview)       │  │  model       │
        └──────┬───────┘  └────────┬─────────┘  └──────┬───────┘
               └───────────────────┼───────────────────┘
                                   ▼
                 quality · latency · tokens · cost · variance
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
      displacement          saving model         snapshot
      scorecard                                  assessment
```

All three deployments sit behind one Foundry endpoint with one authentication model,
one SDK and one bill. In your application code, only the deployment name changes — which
is also your answer on switching cost, demonstrated rather than asserted.

---

## Getting started

### What you need

- An Azure subscription with Microsoft Foundry access
- Contributor or Owner on the target resource group, to create resources and deployments
- Cognitive Services User or higher on the Foundry resource, to run inference with
  Microsoft Entra ID
- Confirmed model availability and quota in your target region
- Python 3.11+, Azure CLI, Bicep CLI

### 1. Deploy the evaluation environment

```bash
az login

az deployment sub create \
  --location <your-region> \
  --template-file infrastructure/main.bicep \
  --parameters infrastructure/parameters/evaluation.bicepparam
```

This creates a Foundry account and project, the three model deployments, role
assignments and diagnostic logging. Authentication is keyless throughout, using
Microsoft Entra ID.

### 2. Point the kit at your current model

```yaml
# config/models.yaml
models:
  flash_ga:
    deployment: DeepSeek-V4-Flash
    role: production_target
  flash_0731:
    deployment: DeepSeek-V4-Flash-0731
    role: preview_candidate
    preview: true
  baseline:
    deployment: <your-current-deployment-name>
    role: incumbent
```

### 3. Describe your workloads

This is the step that determines whether the output is useful. Break your traffic into
segments that reflect how you actually use the model, and set the quality bar each one
has to clear.

```yaml
# config/workload-segments.yaml
segments:
  - name: summarisation
    monthly_requests: 400000
    avg_input_tokens: 6000
    avg_output_tokens: 500
    quality_threshold: 0.90

  - name: classification
    monthly_requests: 250000
    avg_input_tokens: 1200
    avg_output_tokens: 50
    quality_threshold: 0.95

  - name: long_document_qa
    monthly_requests: 60000
    avg_input_tokens: 180000
    avg_output_tokens: 1200
    quality_threshold: 0.88
```

Displacement is decided per segment. A single global pass/fail verdict would hide the
answer you are looking for.

Flash supports a one-million-token input context, so long-document and large-codebase
segments are worth including — the cost advantage grows with context length.

### 4. Add your test cases

Your test cases go in `datasets/customer/`, which is excluded from source control by
default. Nothing you put there is committed or shared.

```json
{
  "id": "sum-014",
  "segment": "summarisation",
  "input": "…a prompt representative of your production traffic…",
  "expected": "…expected outcome, or the criteria a good answer must meet…",
  "check": "deterministic"
}
```

Aim for at least 30 cases per segment. Below roughly 100 cases in total, treat the
results as directional — the reports label them accordingly.

### 5. Run the evaluation

```bash
# Run all three models across every segment
python -m src.evaluation.runner --config config/evaluation.yaml

# Which segments cleared their quality bar
python -m src.evaluation.segmentation \
  --results results/latest.json \
  --output reports/displacement-scorecard.md

# What the move is worth at your volumes
python -m src.reporting.cost \
  --results results/latest.json \
  --segments config/workload-segments.yaml

# Whether the preview snapshot has regressed against GA
python -m src.reporting.snapshot_diff \
  --results results/latest.json \
  --output reports/snapshot-assessment.md
```

---

## How the evaluation is run

You should understand the method before you rely on the numbers.

**Every case runs multiple times.** Reasoning models on Foundry do not support
`temperature`, `top_p`, `presence_penalty` or `repetition_penalty`, so responses are
not deterministic. Each case runs three times by default and the reports show variance
rather than a single sample.

**Objective checks come first.** Schema validation, exact match, numeric tolerance and
unit tests are used wherever the task allows. A model-based judge is used only where
the task is genuinely subjective — and the judge is always a third model, never one of
the models being compared.

**Your prompts are tested twice.** Once exactly as they run today, and once adapted to
reasoning-model guidance — simple, zero-shot, without chain-of-thought scaffolding.
Prompts tuned for your current model can underperform on a reasoning model for reasons
that have nothing to do with capability, so you see both results.

**Reasoning tokens are counted.** Reasoning models produce reasoning content alongside
the answer, and both count toward your token usage and cost. A cheaper per-token rate
can still produce a higher cost per task if responses are verbose, so the headline
metric is **cost per successfully completed task at your quality threshold** — not cost
per million tokens.

**Conversation history is handled correctly.** In multi-turn tests, only the final
answer is carried forward, never the reasoning content. Getting this wrong inflates
both cost and error rates and would distort your results.

---

## What you receive

**Displacement scorecard.** For each workload segment: pass rate against your quality
threshold, quality delta versus your current model, p50 and p95 latency, variance
across repeated runs, and a move / hold / investigate recommendation.

**Cost model.** For each segment: tokens consumed including reasoning content, cost per
completed task, blended cost at your stated volumes, and total projected saving
calculated only on the segments that passed.

**Snapshot assessment.** Generally available Flash versus `-0731`: quality, latency and
cost differences, any behavioural regression, and an adopt-now, wait-for-GA or reject
recommendation.

All three are Markdown documents in `reports/`, suitable for internal circulation.

---

## Repository layout

```text
foundry-deepseek-accelerator/
├── config/
│   ├── models.yaml              # deployments under comparison
│   ├── workload-segments.yaml   # your segments and quality thresholds
│   └── evaluation.yaml          # repeats, judge model, pass criteria
├── infrastructure/
│   ├── main.bicep
│   └── modules/
│       ├── foundry.bicep            # account, project, RBAC, diagnostics
│       └── model-deployment.bicep   # model deployments
├── src/
│   ├── clients/                 # Foundry client, reasoning-output handling
│   ├── evaluation/              # runner, evaluators, segmentation
│   └── reporting/               # cost model, snapshot comparison
├── datasets/
│   ├── templates/               # test case schema and examples
│   └── customer/                # your data — excluded from source control
├── reports/                     # generated outputs
└── tests/
```

---

## Security and data handling

- Authentication uses Microsoft Entra ID throughout. No API keys are stored or
  required by the kit.
- Models run as Foundry Models sold by Azure: hosted and operated by Azure, covered by
  Azure service terms, and billed through your subscription.
- All resources are created in your subscription, in the region you specify.
- Your evaluation data stays in your environment. `datasets/customer/` and `results/`
  are excluded from source control.
- Diagnostic logging is enabled on the Foundry resource by default so you can audit
  every request made during the evaluation.
- Confirm your own content-safety, data-residency and Responsible AI requirements
  before running against production-derived data.

---

## Before you rely on the numbers

- Validate all pricing against the Azure pricing calculator and your own commercial
  agreement. The kit resolves current rates at runtime, but your agreement may differ.
- Re-confirm the release status and capability matrix of `DeepSeek-V4-Flash-0731`
  before adopting it. Preview snapshots change.
- Results are only as representative as the test cases you supply. Invest the effort in
  step 4.