"""Generate a synthetic evaluation dataset with the Microsoft Foundry SDK.

The script asks a Foundry model deployment for new test cases that match the schema
used by datasets/synthetic:

    id, category, prompt, expected_keywords, reference_answer
    illustrative_candidate_response (optional, deliberately weaker answer)

Every generated row is validated locally before it is written, and prompts are
de-duplicated across the run. Live model calls incur Azure charges.

Example:
    python scripts/generate_synthetic_dataset.py --total 1000
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

from dotenv import load_dotenv

KIT_ROOT = Path(__file__).resolve().parents[1]

CATEGORY_GUIDANCE = {
    "Summarisation": (
        "Each prompt asks the model to summarise a short internal policy or notice in one sentence "
        "while preserving specific conditions (durations, thresholds, approvals, schedules). "
        "Vary the policy domain: remote work, expenses, incidents, retention, maintenance, access "
        "reviews, backups, procurement, training, credentials."
    ),
    "Classification": (
        "Each prompt reads exactly: 'Classify this support ticket as billing, access, or reliability. "
        "Return only the label: <ticket text>'. The reference_answer must be the single lowercase label "
        "billing, access, or reliability, and expected_keywords must contain only that label. "
        "Balance the three labels across the batch."
    ),
    "Extraction": (
        "Each prompt asks the model to extract two or three concrete values from one sentence "
        "(identifiers, dates, amounts, times, names, email addresses, regions). "
        "The reference_answer lists the extracted values with short labels, for example "
        "'Incident ID: INC-4821; severity: Sev 1; affected region: West Europe.'"
    ),
}

CATEGORY_FILES = {
    "Summarisation": "summarisation",
    "Classification": "classification",
    "Extraction": "extraction",
}

SYSTEM_PROMPT = (
    "You author synthetic evaluation test cases for comparing large language model deployments. "
    "You return only JSON, never prose, never Markdown code fences. "
    "Use fictional organisations, people, and identifiers; never use real personal data. "
    "Email addresses must use the example.com domain."
)

REQUIRED_FIELDS = ("prompt", "expected_keywords", "reference_answer", "illustrative_candidate_response")


def load_seed_examples(category: str, limit: int = 3) -> list[dict]:
    seed_path = KIT_ROOT / "datasets" / "synthetic" / f"{CATEGORY_FILES[category]}.jsonl"
    if not seed_path.is_file():
        return []
    rows = [json.loads(line) for line in seed_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [
        {key: row[key] for key in ("prompt", "expected_keywords", "reference_answer") if key in row}
        for row in rows[:limit]
    ]


def build_user_prompt(category: str, batch_size: int, seed_examples: list[dict], avoid_prompts: list[str]) -> str:
    sections = [
        f"Generate {batch_size} new synthetic test cases for the category '{category}'.",
        CATEGORY_GUIDANCE[category],
        "Return a JSON object shaped exactly like this, with no other keys:",
        json.dumps(
            {
                "examples": [
                    {
                        "prompt": "The instruction sent to the model under test.",
                        "expected_keywords": ["value that must appear in a correct answer"],
                        "reference_answer": "A fully correct answer containing every expected keyword verbatim.",
                        "illustrative_candidate_response": "A weaker answer that omits at least one expected keyword.",
                    }
                ]
            },
            indent=2,
        ),
        "Rules:\n"
        "- Every string in expected_keywords must appear verbatim inside reference_answer.\n"
        "- expected_keywords holds 1 to 3 short, checkable values, never whole sentences.\n"
        "- illustrative_candidate_response must omit or contradict at least one expected keyword.\n"
        "- Each prompt must be self-contained and must not repeat any earlier prompt.\n"
        "- Vary entities, numbers, dates, and phrasing across the batch.",
    ]
    if seed_examples:
        sections.append("Match the style of these existing examples:\n" + json.dumps(seed_examples, indent=2))
    if avoid_prompts:
        sections.append("Do not repeat or lightly reword any of these prompts:\n" + "\n".join(avoid_prompts))
    return "\n\n".join(sections)


def parse_examples(content: str) -> list[dict]:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text.strip("`")
        text = text.removeprefix("json").strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return []
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return []

    if isinstance(payload, dict):
        payload = payload.get("examples", [])
    return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []


def validate_example(candidate: dict, category: str) -> dict | None:
    for field in REQUIRED_FIELDS:
        if field not in candidate:
            return None

    prompt = candidate["prompt"]
    reference = candidate["reference_answer"]
    weak = candidate["illustrative_candidate_response"]
    keywords = candidate["expected_keywords"]

    if not all(isinstance(value, str) and value.strip() for value in (prompt, reference, weak)):
        return None
    if not isinstance(keywords, list) or not 1 <= len(keywords) <= 3:
        return None
    if not all(isinstance(keyword, str) and keyword.strip() for keyword in keywords):
        return None
    if any(keyword.casefold() not in reference.casefold() for keyword in keywords):
        return None
    if all(keyword.casefold() in weak.casefold() for keyword in keywords):
        return None
    if category == "Classification" and reference.strip().casefold() not in {"billing", "access", "reliability"}:
        return None

    return {
        "category": category,
        "prompt": prompt.strip(),
        "expected_keywords": [keyword.strip() for keyword in keywords],
        "reference_answer": reference.strip(),
        "illustrative_candidate_response": weak.strip(),
    }


def request_batch(client, deployment: str, user_prompt: str, max_tokens: int, temperature: float | None) -> str:
    request = {
        "model": deployment,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "max_completion_tokens": max_tokens,
    }
    if temperature is not None:
        request["temperature"] = temperature
    completion = client.chat.completions.create(**request)
    return completion.choices[0].message.content or ""


def generate_category(
    client,
    deployment: str,
    category: str,
    count: int,
    args: argparse.Namespace,
    rng: random.Random,
) -> list[dict]:
    seed_examples = load_seed_examples(category)
    rows: list[dict] = []
    seen_prompts = {example["prompt"].casefold() for example in seed_examples}
    consecutive_failures = 0

    while len(rows) < count:
        batch_size = min(args.batch_size, count - len(rows))
        recent = [row["prompt"] for row in rows[-args.avoid_window :]]
        user_prompt = build_user_prompt(category, batch_size, seed_examples, recent)

        try:
            content = request_batch(client, deployment, user_prompt, args.max_completion_tokens, args.temperature)
            candidates = parse_examples(content)
        except Exception as exc:  # transient service, quota, or transport failures
            print(f"  {category}: request failed ({type(exc).__name__}: {exc})", flush=True)
            candidates = []

        accepted = 0
        for candidate in candidates:
            if len(rows) >= count:
                break
            example = validate_example(candidate, category)
            if example is None:
                continue
            if example["prompt"].casefold() in seen_prompts:
                continue
            seen_prompts.add(example["prompt"].casefold())
            if rng.random() >= args.weak_answer_ratio:
                example.pop("illustrative_candidate_response")
            rows.append(example)
            accepted += 1

        consecutive_failures = 0 if accepted else consecutive_failures + 1
        print(f"  {category}: {len(rows)}/{count} accepted (+{accepted} this batch)", flush=True)
        if consecutive_failures >= args.max_empty_batches:
            raise RuntimeError(
                f"{category}: {consecutive_failures} consecutive batches produced no usable examples."
            )

    prefix = CATEGORY_FILES[category]
    for index, row in enumerate(rows, start=1):
        row["id"] = f"{prefix}-{index:04d}"
    return [{"id": row.pop("id"), **row} for row in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--total", type=int, default=1_000, help="Total examples across all categories.")
    parser.add_argument("--batch-size", type=int, default=10, help="Examples requested per model call.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=KIT_ROOT / "datasets" / "synthetic-large",
        help="Directory that receives one JSONL file per category.",
    )
    parser.add_argument("--deployment", default="", help="Deployment used to generate data (default: MODEL_DEPLOYMENT_NAME).")
    parser.add_argument("--temperature", type=float, default=None, help="Optional sampling temperature.")
    parser.add_argument("--max-completion-tokens", type=int, default=4_000, help="Completion token cap per call.")
    parser.add_argument("--request-timeout", type=float, default=120.0, help="Per-request timeout in seconds.")
    parser.add_argument("--max-retries", type=int, default=2, help="SDK retries per request.")
    parser.add_argument("--max-empty-batches", type=int, default=5, help="Abort after this many unusable batches.")
    parser.add_argument("--avoid-window", type=int, default=20, help="Recent prompts sent back as a do-not-repeat list.")
    parser.add_argument("--weak-answer-ratio", type=float, default=0.12, help="Share of rows keeping the weaker answer.")
    parser.add_argument("--seed", type=int, default=20260828, help="Seed for the weaker-answer selection.")
    args = parser.parse_args()

    if args.total < len(CATEGORY_GUIDANCE):
        parser.error(f"--total must be at least {len(CATEGORY_GUIDANCE)}.")

    env_file = Path(os.getenv("FDKIT_ENV_FILE", str(KIT_ROOT / ".env"))).expanduser()
    load_dotenv(dotenv_path=env_file)

    endpoint = os.getenv("PROJECT_ENDPOINT", "")
    deployment = args.deployment or os.getenv("MODEL_DEPLOYMENT_NAME", "")
    if not endpoint or not deployment:
        print(f"PROJECT_ENDPOINT and MODEL_DEPLOYMENT_NAME are required in {env_file}", file=sys.stderr)
        return 1

    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    categories = list(CATEGORY_GUIDANCE)
    base, remainder = divmod(args.total, len(categories))
    counts = [base + (1 if index < remainder else 0) for index in range(len(categories))]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)

    print(f"Generating {args.total} examples with deployment '{deployment}' (this makes live model calls).")

    credential = DefaultAzureCredential()
    project_client = AIProjectClient(endpoint=endpoint, credential=credential)
    openai_client = project_client.get_openai_client().with_options(
        timeout=args.request_timeout,
        max_retries=args.max_retries,
    )

    try:
        for category, count in zip(categories, counts):
            rows = generate_category(openai_client, deployment, category, count, args, rng)
            output_path = args.output_dir / f"{CATEGORY_FILES[category]}.jsonl"
            with output_path.open("w", encoding="utf-8") as output_file:
                for row in rows:
                    output_file.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"{output_path}: {len(rows)} examples")
    finally:
        for resource in (openai_client, project_client, credential):
            close = getattr(resource, "close", None)
            if callable(close):
                close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
