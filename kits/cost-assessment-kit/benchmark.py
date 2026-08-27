
import csv, json, time
from openai import OpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider


endpoint = "https://foundry-hosted-demos-73868ea3.services.ai.azure.com/openai/v1"

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), 
    "https://ai.azure.com/.default")


MODELS = [
    "DeepSeek-V4-Flash",
    "gpt-5.4",
    "gpt-4.1-mini"
]

MODEL_PRICING_USD_PER_1M = {
    "DeepSeek-V4-Flash": {"input": 0.19, "output": 0.51},
    "gpt-5.4": {"input": 2.50, "output": 15.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
}

client = OpenAI(
    base_url=endpoint,
    api_key=token_provider
)

with open('prompts.jsonl') as f:
    prompts = [json.loads(x) for x in f]

rows = []
for model in MODELS:
    for p in prompts:
        start = time.time()
        response = client.chat.completions.create(
            model=model,
            messages=[{'role':'user','content':p['prompt']}],
            temperature=0,
        )
        latency_ms = round((time.time()-start)*1000,2)
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        pricing = MODEL_PRICING_USD_PER_1M[model]
        input_cost_usd = input_tokens * pricing["input"] / 1_000_000
        output_cost_usd = output_tokens * pricing["output"] / 1_000_000
        rows.append({
            'model': model,
            'prompt_id': p['id'],
            'latency_ms': latency_ms,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': response.usage.total_tokens,
            'input_price_per_1m_usd': pricing["input"],
            'output_price_per_1m_usd': pricing["output"],
            'input_cost_usd': f"{input_cost_usd:.10f}",
            'output_cost_usd': f"{output_cost_usd:.10f}",
            'total_cost_usd': f"{input_cost_usd + output_cost_usd:.10f}",
        })

with open('results.csv','w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print('done')




print(f"answer: {response.output[0]}")
