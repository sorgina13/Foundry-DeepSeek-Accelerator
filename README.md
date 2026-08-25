# Microsoft Foundry DeepSeek Accelerator

A modular accelerator for evaluating, deploying and operationalising DeepSeek on Microsoft Foundry.

The project helps customers answer:

1. Is DeepSeek good enough for my workload?
2. How much could we save?
3. Can we deploy it securely?
4. How quickly can we deploy?
5. Will it perform reliably at scale?
6. How will we govern usage and cost?
7. Can we avoid model lock-in?
8. What is the path to production?

## Initial scope

The first release focuses on three outcomes:

- Repeatable DeepSeek deployment
- Customer-specific comparison against a frontier baseline
- Quality, latency, token and cost scorecard

Security hardening, load testing, APIM governance and production-readiness
assessment are added as independent modules.

## Architecture

The accelerator uses:

- Microsoft Foundry resource and project
- DeepSeek and baseline model deployments
- Azure OpenAI-compatible v1 API
- Microsoft Entra ID authentication
- Python evaluation harness
- Application Insights telemetry
- Bicep infrastructure automation

## Repository structure

- `config/`: Models, pricing and evaluation configuration
- `infrastructure/`: Modular Bicep deployment
- `src/clients/`: Provider-independent model clients
- `src/evaluation/`: Dataset execution and scoring
- `src/telemetry/`: Token, latency and cost capture
- `src/load_testing/`: Concurrency and reliability tests
- `src/reporting/`: Scorecard, TCO and readiness reports
- `datasets/`: Customer evaluation datasets
- `policies/`: APIM, content-safety and Azure Policy assets
- `notebooks/`: Guided evaluation workflow
- `reports/`: Generated decision documents

## Prerequisites

- Azure subscription
- Microsoft Foundry access
- Permissions to deploy Foundry resources and models
- Cognitive Services User or equivalent data-plane access
- Python 3.11+
- Azure CLI
- Bicep CLI

## Configuration

Copy the environment template:

```bash
cp .env.example .env# Foundry-DeepSeek-Accelerator
