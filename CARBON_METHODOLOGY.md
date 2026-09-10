# Carbon estimation method

Research date: 2026-09-10. This is an **operational serving-electricity scenario**, not measured provider emissions or a full life-cycle footprint. All reported tons are **metric tons of CO₂ (1,000 kg)**. Low and high scenarios are sensitivity tests, not confidence intervals or guaranteed bounds.

## Why use the electricity shortcut?

Closed-model parameter counts are undisclosed. Benchmark scores do not determine them: DeepSeek-V3 (37B active / 671B total parameters) and Llama 3.1 405B (405B active) score 88.5 and 88.6 on the same published MMLU comparison. Similar capability can therefore involve more than ten times the active weights. [DeepSeek's model card](https://huggingface.co/deepseek-ai/DeepSeek-V3)

Qwen3-235B-A22B-Thinking-2507 reports GPQA 81.1, versus o4-mini 81.4, o3 83.3, and Claude 4 Opus Thinking 79.6 in its comparison. These are useful capability comparisons, not an inverse model-size estimator. Test-time reasoning, training, architecture, and evaluation settings matter. [Qwen's model card](https://huggingface.co/Qwen/Qwen3-235B-A22B-Thinking-2507)

The dashboard therefore exposes **open-model compute proxies**, keeping actual proprietary parameters unknown. It does not present proxy weights as the closed model's estimated total weights.

| Scenario family | Open-model reference | Total / active parameters | Approximate FLOPs per million fresh tokens |
|---|---|---|---|
| Efficient | gpt-oss-120b | 117B / 5.1B | 1.02 × 10¹⁶ |
| Mainstream | Qwen3-235B-A22B | 235B / 22B | 4.40 × 10¹⁶ |
| Frontier | DeepSeek-V3 | 671B / 37B | 7.40 × 10¹⁶ |

OpenAI reports gpt-oss-120b performing near o4-mini despite only 5.1B active parameters. [OpenAI's release](https://openai.com/index/introducing-gpt-oss/)

Compute proxy: `2 × active parameters × token count`. This is approximate matrix-multiplication work. It excludes attention's context-length dependence, memory traffic, routing, speculative generation, and serving overhead. Cached input does not repeat a full fresh forward pass. **FLOPs are operations; FLOP/s is a rate.** Electricity cannot be recovered by dividing by peak GPU FLOP/s without utilization, hardware, precision, batching, and power measurements. [Efficiently Scaling Transformer Inference](https://arxiv.org/html/2211.05102v1)

## Observed model assignments

These are analyst-selected scenario families, not benchmark-derived parameter estimates or measurements. Within a family, different models receive the same coefficients because there is insufficient evidence to justify finer precision.

| Recorded model | Family |
|---|---|
| claude-haiku-4-5-20251001 | Efficient |
| claude-sonnet-5 | Mainstream |
| gpt-5.6-terra | Mainstream |
| claude-opus-4-8 | Frontier |
| claude-opus-5 | Frontier |
| claude-fable-5 | Frontier |
| claude-fable-5-1 | Frontier |
| gpt-5.5 | Frontier |
| gpt-5.6-sol | Frontier |
| gpt-6-astra | Frontier |
| codex-auto-review | Frontier fallback: underlying model unidentified |
| unknown or any other new label | Frontier fallback: unidentified |
| zero-token synthetic messages | No attributed energy |

Vendor positioning supports broad efficient/balanced/frontier distinctions only: [OpenAI model catalog](https://developers.openai.com/api/docs/models), [Anthropic Haiku 4.5](https://www.anthropic.com/news/claude-haiku-4-5), [Fable](https://www.anthropic.com/claude/fable), [Opus 5](https://www.anthropic.com/news/claude-opus-5). Haiku matching an older Sonnet's coding capability is another reason performance improvements cannot be converted directly into parameter growth.

## Measured energy context

ML.ENERGY's energy-optimal B200 configurations report these approximate GPU energy intensities for reasoning workloads:

| Open model | J / output token | kWh / million output tokens |
|---|---|---|
| GPT OSS 120B | 0.0397 | 0.0110 |
| Qwen3 235B A22B FP8 | 0.4177 | 0.1160 |
| DeepSeek V3.1 | 1.3351 | 0.3709 |
| DeepSeek R1 | 2.3762 | 0.6601 |

These are **whole-response GPU energy divided by output tokens**, including amortized prefill, not isolated decode coefficients. They cannot be used as measured output costs while also adding measured prefill. They contextualize the magnitude of the scenarios below; they are not measurements of the user's models. [ML.ENERGY leaderboard](https://ml.energy/leaderboard/)

Batching and workload substantially change energy per token. The benchmark authors report Qwen3 32B at 0.151 J/output token for text conversation versus 0.312 for reasoning, with different energy-optimal batches. [Authors' measurement analysis](https://ml.energy/blog/measurement/energy/diagnosing-inference-energy-consumption-with-the-mlenergy-leaderboard-v30/)

Google measured 0.14 Wh for active accelerators versus 0.24 Wh with broader serving overhead for its median Gemini Apps text prompt. This illustrates why GPU-only measurements omit significant energy; it does not establish OpenAI/Anthropic overhead. [Google primary study](https://arxiv.org/html/2508.15734v1)

## Electricity assumptions

All entries below are **assumed facility-inclusive kWh per million tokens**. They include an allowance for serving overhead, so no additional PUE multiplier is applied. None is a published coefficient for these closed models.

| Family | Token category | Low | Central | High |
|---|---|---:|---:|---:|
| Efficient | Fresh input/cache creation | 0.005 | 0.04 | 0.5 |
| Efficient | Cached input | 0.00005 | 0.002 | 0.1 |
| Efficient | Output | 0.05 | 0.2 | 1 |
| Mainstream | Fresh input/cache creation | 0.02 | 0.2 | 2 |
| Mainstream | Cached input | 0.0002 | 0.01 | 0.4 |
| Mainstream | Output | 0.2 | 1 | 4 |
| Frontier | Fresh input/cache creation | 0.05 | 0.4 | 4 |
| Frontier | Cached input | 0.0005 | 0.02 | 0.8 |
| Frontier | Output | 0.5 | 2 | 8 |

The assumed fresh/output ratios are 0.1 / 0.2 / 0.5; cached/fresh ratios are 0.01 / 0.05 / 0.2. These deliberately broad sensitivity assumptions reflect unknown cache transfers, memory, context length, batching, and deployment. **API price discounts are not energy discounts.** Prompt caching reuses previously computed KV state rather than repeating prefill, but has nonzero storage, transfer, and attention costs. [Claude prompt caching documentation](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)

Normalized input already includes cache creation. Subtract cache reads once to obtain fresh input. Output already includes recorded reasoning tokens; do not add them again. Unrecorded hidden work is not measurable here. The estimates follow retained usage logs, including all four agent roles.

```
fresh = input - cached_input
facility_kWh = (fresh × fresh_rate + cached_input × cached_rate + output × output_rate) / 1,000,000
metric_tons_CO2 = facility_kWh × grid_kg_CO2_per_kWh / 1,000
```

## Grid and flights

Low / central / high electricity intensities are **0.05 / 0.445 / 0.8 kg CO₂/kWh**. The central factor uses IEA's 2024 global electricity-generation average of 445 g CO₂/kWh. Actual serving locations and hours are unknown; the user's location is not the data-center location. Low/high are assumed alternative grids. [IEA Electricity 2025](https://www.iea.org/reports/electricity-2025/emissions)

One flight equivalent means **one passenger flying one-way economy from LAX to JFK**, approximated as 3,974 km great-circle distance × 1.08 distance uplift × 63.2 g CO₂/passenger-km ≈ 0.271 metric tons; use **0.27 tons**. This is a generic long-haul economy proxy, not a route-specific flight measurement. The CO₂ factor and 8% uplift come from [DESNZ 2026 methodology, Table 43](https://assets.publishing.service.gov.uk/media/6a2940543b15d05a7ce3202e/2026-GHG-conversion-factors-methodology-report.pdf).

Both sides compare CO₂ only. Flight equivalents exclude contrails and other non-CO₂ warming, upstream fuel, and aircraft manufacture. [ICAO's calculator likewise distinguishes engine CO₂](https://icec.icao.int/FAQ). This estimate excludes model training allocation, hardware manufacture, external tools, network/client electricity, and life-cycle effects. It is a partial operational footprint, not total climate impact.

## Changing assumptions

The dashboard selector changes all low/central/high assumptions together. To isolate grid sensitivity or choose another family per model, set the optional `carbon` section in your gitignored `config.json` and restart:

```json
"carbon": {
  "grid_kg_co2_per_kwh": {"low": 0.05, "central": 0.445, "high": 0.8},
  "flight_tonnes_co2": 0.27,
  "model_profiles": {"codex-auto-review": "mainstream"}
}
```

The example profile override is optional, not evidence of the reviewer's model. Scenario coefficients and citations live in `carbon.py`. No usage or carbon-report data is committed to GitHub.
