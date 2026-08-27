import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_MODELS = [
    "deepseek-v4-flash-3107",
    "gpt-5-sol",
    "gpt-5-mini",
]
TERMINAL_STATUSES = {"completed", "failed", "canceled", "cancelled"}
REQUIRED_FIELDS = {
    "name",
    "prompt_id",
    "category",
    "difficulty",
    "query",
    "ground_truth",
    "expected_behavior",
    "criteria",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create and optionally run comparable Microsoft Foundry model evaluations."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).with_name("foundry_eval_dataset.jsonl"),
    )
    parser.add_argument(
        "--project-endpoint",
        default=os.getenv("AZURE_AI_PROJECT_ENDPOINT"),
        help="Foundry project endpoint; defaults to AZURE_AI_PROJECT_ENDPOINT.",
    )
    parser.add_argument(
        "--judge-deployment",
        default=os.getenv("AZURE_AI_JUDGE_DEPLOYMENT"),
        help="Fixed judge deployment; defaults to AZURE_AI_JUDGE_DEPLOYMENT.",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=DEFAULT_MODELS,
        help="Foundry model deployment names to evaluate.",
    )
    parser.add_argument("--dataset-name", default="foundry-model-benchmark-100")
    parser.add_argument(
        "--dataset-version",
        help="Dataset version. Defaults to the first 12 characters of the file SHA-256.",
    )
    parser.add_argument("--evaluation-name", default="foundry-model-comparison")
    parser.add_argument(
        "--evaluator-name", default="behavioral_adherence"
    )
    parser.add_argument(
        "--profile",
        choices=("core", "full"),
        default="core",
        help="core: quality/reference/custom checks; full: core plus five safety checks.",
    )
    parser.add_argument("--max-completion-tokens", type=int, default=2048)
    parser.add_argument("--poll-seconds", type=int, default=10)
    parser.add_argument(
        "--output-dir", type=Path, default=Path(__file__).with_name("eval_results")
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the local JSONL without authenticating or creating assets.",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Upload the dataset and create evaluator/evaluation assets without starting runs.",
    )
    return parser.parse_args()


def validate_dataset(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError(f"Dataset does not exist: {path}")

    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON on line {line_number}: {error}") from error

        missing = REQUIRED_FIELDS - row.keys()
        if missing:
            raise ValueError(
                f"Line {line_number} is missing fields: {', '.join(sorted(missing))}"
            )
        if not isinstance(row["criteria"], list) or not row["criteria"]:
            raise ValueError(f"Line {line_number} criteria must be a nonempty list")
        for criterion in row["criteria"]:
            if not isinstance(criterion, dict) or not all(
                isinstance(criterion.get(key), str) and criterion[key].strip()
                for key in ("name", "instruction")
            ):
                raise ValueError(
                    f"Line {line_number} has an invalid criterion; name and instruction are required"
                )
        rows.append(row)

    if len(rows) != 100:
        raise ValueError(f"Expected 100 rows, found {len(rows)}")
    for key in ("name", "prompt_id"):
        values = [row[key] for row in rows]
        if len(values) != len(set(values)):
            raise ValueError(f"Dataset contains duplicate {key} values")

    category_counts = Counter(row["category"] for row in rows)
    if len(category_counts) != 10 or set(category_counts.values()) != {10}:
        raise ValueError(
            f"Expected 10 categories with 10 rows each, found {dict(category_counts)}"
        )
    return rows


def dataset_version(path: Path, override: str | None) -> str:
    if override:
        return override
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def create_behavioral_evaluator(project_client, name: str):
    from azure.ai.projects.models import EvaluatorCategory, EvaluatorDefinitionType

    return project_client.beta.evaluators.create_version(
        name=name,
        evaluator_version={
            "name": name,
            "categories": [EvaluatorCategory.QUALITY],
            "display_name": "Behavioral adherence",
            "description": "Scores a response against each row's expected behavior and criteria.",
            "definition": {
                "type": EvaluatorDefinitionType.PROMPT,
                "prompt_text": (
                    "Evaluate how well the response satisfies the requested behavior and every "
                    "criterion. Use the ground truth as reference, while respecting exact-format "
                    "requirements. Do not treat inability to verify a current sourced fact as proof "
                    "that it is false; flag that uncertainty in the reason.\n\n"
                    "Query:\n{{query}}\n\nResponse:\n{{response}}\n\n"
                    "Ground truth:\n{{ground_truth}}\n\n"
                    "Expected behavior:\n{{expected_behavior}}\n\n"
                    "Criteria:\n{{criteria}}\n\n"
                    "Score from 1 to 5: 1 misses the task, 3 partially satisfies it, and 5 fully "
                    "satisfies every requirement. Return JSON with integer result and brief reason."
                ),
                "init_parameters": {
                    "type": "object",
                    "properties": {
                        "deployment_name": {"type": "string"},
                        "threshold": {"type": "number"},
                    },
                    "required": ["deployment_name", "threshold"],
                },
                "data_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "response": {"type": "string"},
                        "ground_truth": {"type": "string"},
                        "expected_behavior": {"type": "string"},
                        "criteria": {"type": "array"},
                    },
                    "required": [
                        "query",
                        "response",
                        "ground_truth",
                        "expected_behavior",
                        "criteria",
                    ],
                },
                "metrics": {
                    "result": {
                        "type": "ordinal",
                        "desirable_direction": "increase",
                        "min_value": 1,
                        "max_value": 5,
                    }
                },
            },
        },
    )


def evaluator(
    name: str,
    evaluator_name: str,
    data_mapping: dict[str, str],
    judge_deployment: str | None = None,
    threshold: int | None = None,
) -> dict:
    criterion = {
        "type": "azure_ai_evaluator",
        "name": name,
        "evaluator_name": evaluator_name,
        "data_mapping": data_mapping,
    }
    if judge_deployment:
        criterion["initialization_parameters"] = {
            "deployment_name": judge_deployment
        }
        if threshold is not None:
            criterion["initialization_parameters"]["threshold"] = threshold
    return criterion


def build_testing_criteria(
    judge_deployment: str, custom_evaluator_name: str, profile: str
) -> list[dict]:
    query_response = {
        "query": "{{item.query}}",
        "response": "{{sample.output_text}}",
    }
    criteria = [
        evaluator("coherence", "builtin.coherence", query_response, judge_deployment),
        evaluator("relevance", "builtin.relevance", query_response, judge_deployment),
        evaluator(
            "response_completeness",
            "builtin.response_completeness",
            {
                "response": "{{sample.output_text}}",
                "ground_truth": "{{item.ground_truth}}",
            },
            judge_deployment,
        ),
        evaluator(
            "f1",
            "builtin.f1_score",
            {
                "response": "{{sample.output_text}}",
                "ground_truth": "{{item.ground_truth}}",
            },
        ),
        evaluator(
            "behavioral_adherence",
            custom_evaluator_name,
            {
                "query": "{{item.query}}",
                "response": "{{sample.output_text}}",
                "ground_truth": "{{item.ground_truth}}",
                "expected_behavior": "{{item.expected_behavior}}",
                "criteria": "{{item.criteria}}",
            },
            judge_deployment,
            threshold=4,
        ),
    ]
    if profile == "full":
        for safety_name in (
            "violence",
            "sexual",
            "self_harm",
            "hate_unfairness",
            "indirect_attack",
        ):
            criteria.append(
                evaluator(
                    safety_name,
                    f"builtin.{safety_name}",
                    query_response,
                )
            )
    return criteria


def data_source_config():
    from openai.types.eval_create_params import DataSourceConfigCustom

    return DataSourceConfigCustom(
        type="custom",
        item_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "prompt_id": {"type": "string"},
                "category": {"type": "string"},
                "difficulty": {"type": "string"},
                "query": {"type": "string"},
                "context": {"type": "string"},
                "ground_truth": {"type": "string"},
                "expected_behavior": {"type": "string"},
                "criteria": {"type": "array"},
            },
            "required": [
                "name",
                "prompt_id",
                "category",
                "difficulty",
                "query",
                "ground_truth",
                "expected_behavior",
                "criteria",
            ],
        },
        include_sample_schema=True,
    )


def model_data_source(dataset_id: str, model: str, max_tokens: int) -> dict:
    return {
        "type": "azure_ai_target_completions",
        "source": {"type": "file_id", "id": dataset_id},
        "input_messages": {
            "type": "template",
            "template": [
                {
                    "type": "message",
                    "role": "user",
                    "content": {
                        "type": "input_text",
                        "text": "{{item.query}}",
                    },
                }
            ],
        },
        "target": {
            "type": "azure_ai_model",
            "model": model,
            "sampling_params": {"max_completion_tokens": max_tokens},
        },
    }


def wait_for_run(openai_client, evaluation_id: str, run, poll_seconds: int):
    while run.status not in TERMINAL_STATUSES:
        print(f"  {run.name}: {run.status}")
        time.sleep(poll_seconds)
        run = openai_client.evals.runs.retrieve(
            eval_id=evaluation_id, run_id=run.id
        )
    return run


def write_results(openai_client, evaluation_id: str, run, output_path: Path) -> None:
    items = list(
        openai_client.evals.runs.output_items.list(
            eval_id=evaluation_id, run_id=run.id
        )
    )
    output_path.write_text(
        json.dumps([item.model_dump(mode="json") for item in items], indent=2),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    try:
        rows = validate_dataset(args.dataset)
    except ValueError as error:
        print(f"Validation failed: {error}", file=sys.stderr)
        return 2

    categories = Counter(row["category"] for row in rows)
    print(f"Validated {len(rows)} rows across {len(categories)} balanced categories.")
    if args.validate_only:
        return 0
    if not args.project_endpoint:
        print(
            "Missing --project-endpoint or AZURE_AI_PROJECT_ENDPOINT.", file=sys.stderr
        )
        return 2
    if not args.judge_deployment:
        print(
            "Missing --judge-deployment or AZURE_AI_JUDGE_DEPLOYMENT.",
            file=sys.stderr,
        )
        return 2

    try:
        from azure.ai.projects import AIProjectClient
        from azure.identity import DefaultAzureCredential
    except ImportError as error:
        print(
            "Azure SDK dependencies are missing. Install requirements.txt before creating assets.",
            file=sys.stderr,
        )
        print(f"Import error: {error}", file=sys.stderr)
        return 2

    version = dataset_version(args.dataset, args.dataset_version)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(
            endpoint=args.project_endpoint, credential=credential
        ) as project_client,
        project_client.get_openai_client() as openai_client,
    ):
        print(f"Uploading dataset {args.dataset_name}:{version}...")
        dataset = project_client.datasets.upload_file(
            name=args.dataset_name,
            version=version,
            file_path=str(args.dataset),
        )

        print(f"Creating {args.evaluator_name} evaluator version...")
        custom_evaluator = create_behavioral_evaluator(
            project_client, args.evaluator_name
        )

        print("Creating reusable evaluation definition...")
        evaluation = openai_client.evals.create(
            name=f"{args.evaluation_name}-{timestamp}",
            data_source_config=data_source_config(),
            testing_criteria=build_testing_criteria(
                args.judge_deployment, args.evaluator_name, args.profile
            ),
        )

        manifest = {
            "project_endpoint": args.project_endpoint,
            "dataset": {
                "name": dataset.name,
                "version": version,
                "id": dataset.id,
            },
            "custom_evaluator": {
                "name": custom_evaluator.name,
                "version": custom_evaluator.version,
            },
            "evaluation": {"name": evaluation.name, "id": evaluation.id},
            "judge_deployment": args.judge_deployment,
            "profile": args.profile,
            "target_models": args.models,
            "runs": [],
        }
        manifest_path = args.output_dir / f"manifest-{timestamp}.json"

        if args.prepare_only:
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            print(f"Assets created. Manifest: {manifest_path}")
            return 0

        for model in args.models:
            print(f"Starting evaluation run for {model}...")
            run = openai_client.evals.runs.create(
                eval_id=evaluation.id,
                name=f"{model}-{timestamp}",
                data_source=model_data_source(
                    dataset.id, model, args.max_completion_tokens
                ),
            )
            run = wait_for_run(
                openai_client, evaluation.id, run, args.poll_seconds
            )
            run_info = {
                "model": model,
                "run_id": run.id,
                "status": run.status,
                "report_url": getattr(run, "report_url", None),
            }
            manifest["runs"].append(run_info)
            print(f"  {model}: {run.status} ({run_info['report_url'] or 'no report URL'})")
            if run.status == "completed":
                write_results(
                    openai_client,
                    evaluation.id,
                    run,
                    args.output_dir / f"{model}-{timestamp}.json",
                )

        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"Run manifest: {manifest_path}")
        return 0 if all(run["status"] == "completed" for run in manifest["runs"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())