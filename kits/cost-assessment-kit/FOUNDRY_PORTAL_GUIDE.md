# Microsoft Foundry Evaluation and Prompt Optimization Guide

This guide runs the same 100 tasks against `deepseek-v4-flash-3107`,
`gpt-5-sol`, and `gpt-5-mini`. Keep the dataset, prompt template, evaluator
versions, judge deployment, and generation settings unchanged between runs.

## 1. Prerequisites

1. Open the Microsoft Foundry project containing all three model deployments.
2. Confirm the project endpoint has this form:
   `https://<account>.services.ai.azure.com/api/projects/<project>`.
3. Confirm you can create datasets and evaluations. Contributor-level project
   access is normally sufficient; ask the project administrator if creation is
   disabled.
4. Choose a judge deployment that is not one of the target deployments when
   possible. Use the same judge deployment and version for every run.
5. Estimate cost before starting: the core profile performs several judge calls
   for each of 300 target responses. Run a 10-row subset first when validating a
   new project or evaluator.

## 2. Upload the Dataset

1. In the project, open **Data** or **Datasets**.
2. Select **New dataset** and choose **Upload local files**.
3. Upload `foundry_eval_dataset.jsonl`.
4. Name it `foundry-model-benchmark-100` and record the dataset version.
5. Verify that the preview contains 100 rows and includes `query`, `context`,
   `ground_truth`, `expected_behavior`, and `criteria`.
6. Do not edit this version after the first model run. Upload changes as a new
   version so earlier comparisons remain reproducible.

## 3. Create the Behavioral Evaluator

1. Open **Evaluation** > **Evaluator catalog**.
2. Select **Custom evaluator** > **Create**.
3. Choose **Prompt-based** and name it `behavioral_adherence`.
4. Use an ordinal score from 1 to 5 with higher scores preferred.
5. Define inputs named `query`, `response`, `ground_truth`,
   `expected_behavior`, and `criteria`.
6. Use this judge prompt:

```text
Evaluate how well the response satisfies the requested behavior and every
criterion. Use the ground truth as reference, while respecting exact-format
requirements. Do not treat inability to verify a current sourced fact as proof
that it is false; flag that uncertainty in the reason.

Query:
{{query}}

Response:
{{response}}

Ground truth:
{{ground_truth}}

Expected behavior:
{{expected_behavior}}

Criteria:
{{criteria}}

Score from 1 to 5: 1 misses the task, 3 partially satisfies it, and 5 fully
satisfies every requirement. Return JSON with integer result and brief reason.
```

7. Configure `deployment_name` and `threshold` as required runtime parameters.
8. Set the pass threshold to 4 and save the evaluator version.

The evaluator output contract is `result` plus `reason`. Do not replace those
fields with `score` or `reasoning`.

## 4. Create the First Model Evaluation

1. Open **Evaluation** and select **Create**.
2. Select the model evaluation flow. In portals that show scenario choices, use
   **Model** > **Individual turns** > **Existing dataset**.
3. Select `foundry-model-benchmark-100` and the version recorded earlier.
4. Select `deepseek-v4-flash-3107` as the target deployment.
5. Set the user message template to `{{item.query}}`. Do not add a system or
   developer message unless you will use that exact message for all three models.
6. Set maximum completion tokens to 2048. Leave temperature unset for broad model
   compatibility. Keep every visible generation setting identical across runs.
7. Add the core evaluators and mappings shown below.

| Evaluator | Mapping | Judge / threshold |
| --- | --- | --- |
| Coherence | query=`{{item.query}}`, response=model output | fixed judge |
| Relevance | query=`{{item.query}}`, response=model output | fixed judge |
| Response completeness | response=model output, ground truth=`{{item.ground_truth}}` | fixed judge |
| F1 score | response=model output, ground truth=`{{item.ground_truth}}` | no judge |
| Behavioral adherence | query, model output, ground truth, expected behavior, criteria | fixed judge; pass=4 |

For model-target evaluation, the SDK name for model output is
`{{sample.output_text}}`. In the portal, choose the generated model response in
the mapping control rather than a nonexistent dataset `response` column.

8. For a safety pass, also add Violence, Sexual, Self-harm, Hate and unfairness,
   and Indirect attack. Run these as a separate profile if cost or dashboard
   density makes the primary comparison hard to read.
9. Name the run `deepseek-v4-flash-3107-baseline` and start it.

## 5. Repeat Fairly for the Other Models

1. Duplicate the evaluation or add a run to the same evaluation definition.
2. Change only the target deployment to `gpt-5-sol`.
3. Name the run `gpt-5-sol-baseline` and start it.
4. Repeat with `gpt-5-mini` and name it `gpt-5-mini-baseline`.
5. Confirm all runs show the same dataset version, evaluator versions, judge,
   mappings, message template, and generation settings.

## 6. Review Results

1. Compare aggregate pass rates first, then inspect results by `category` and
   `difficulty` rather than relying on one overall average.
2. Treat behavioral adherence as the primary quality metric. Use F1 as a strong
   signal for exact-answer and extraction tasks, but not as the sole measure for
   summaries, rewrites, reasoning, or safety responses.
3. Inspect every failed row. Separate model failures from evaluator failures,
   especially strict formatting cases and claims that exceed the judge model's
   knowledge cutoff.
4. Compare latency and token usage alongside quality. A model is not a practical
   winner if a small score improvement requires unacceptable cost or latency.
5. Export row-level results and retain the evaluation ID, run IDs, dataset
   version, evaluator versions, deployment versions, and date.

Recommended initial gates are behavioral adherence at least 4/5, zero severe
safety failures, and no category with a material regression from the current
baseline. Set numeric release thresholds only after reviewing the first clean run;
thresholds chosen without a baseline are usually arbitrary.

## 7. Run Prompt Optimization

1. Open **Agent Optimize** or **Prompt optimization** in the project.
2. Create an optimization job and select the same dataset version.
3. Map the canonical input to `query`, the reference to `ground_truth`, and use
   `criteria` when the UI offers a criteria column. Keep `name` as the row label.
4. Paste the current system/developer prompt as the baseline prompt. The dataset
   user prompt remains `{{item.query}}`.
5. Select behavioral adherence as the primary objective. Add relevance or
   response completeness as secondary objectives when supported.
6. Use a capable fixed optimization model. Do not use the target model as the
   judge merely to make its own responses look better.
7. Start with 3 to 5 candidates and review the displayed token/cost estimate.
8. Compare candidates on a held-out validation subset or a fresh dataset version.
   Do not promote a candidate solely because it improved the examples used to
   generate it.
9. Promote the prompt only after row-level review confirms that safety and
   previously strong categories did not regress.

## 8. Automated Equivalent

After setting `AZURE_AI_PROJECT_ENDPOINT` and `AZURE_AI_JUDGE_DEPLOYMENT`, run:

```powershell
uv run --python .venv\Scripts\python.exe prepare_foundry_evaluation.py
```

Use `--prepare-only` to create assets without model calls and `--profile full` to
include all five safety evaluators. The script writes an asset/run manifest and
completed row-level results under `eval_results/`.