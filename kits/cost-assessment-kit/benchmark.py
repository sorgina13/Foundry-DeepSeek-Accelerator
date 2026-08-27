
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
        rows.append({
            'model': model,
            'prompt_id': p['id'],
            'latency_ms': latency_ms,
            'input_tokens': response.usage.prompt_tokens,
            'output_tokens': response.usage.completion_tokens,
            'total_tokens': response.usage.total_tokens
        })

with open('results.csv','w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print('done')




print(f"answer: {response.output[0]}")
