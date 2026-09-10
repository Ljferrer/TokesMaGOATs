"""Transparent operational-electricity scenarios, not provider measurements.

See CARBON_METHODOLOGY.md for evidence, assumptions, and scope.
All coefficients include facility/serving overhead; do not add PUE again.
"""
SCENARIOS = ('low', 'central', 'high')
GRID = dict(zip(SCENARIOS, (0.05, 0.445, 0.8)))  # kg CO2 / kWh
FLIGHT_TONNES = 0.27  # one passenger, one-way economy LAX–JFK proxy
PROFILES = {
    'efficient': {'input': (.005, .04, .5), 'cached': (.00005, .002, .1), 'output': (.05, .2, 1),
                  'proxy': 'gpt-oss-120b', 'total_b': 117, 'active_b': 5.1},
    'mainstream': {'input': (.02, .2, 2), 'cached': (.0002, .01, .4), 'output': (.2, 1, 4),
                   'proxy': 'Qwen3-235B-A22B', 'total_b': 235, 'active_b': 22},
    'frontier': {'input': (.05, .4, 4), 'cached': (.0005, .02, .8), 'output': (.5, 2, 8),
                 'proxy': 'DeepSeek-V3', 'total_b': 671, 'active_b': 37},
}
MODEL_PROFILES = {
    'claude-haiku-4-5-20251001': 'efficient',
    'claude-sonnet-5': 'mainstream', 'gpt-5.6-terra': 'mainstream',
    'claude-opus-4-8': 'frontier', 'claude-opus-5': 'frontier',
    'claude-fable-5': 'frontier', 'claude-fable-5-1': 'frontier',
    'gpt-5.5': 'frontier', 'gpt-5.6-sol': 'frontier', 'gpt-6-astra': 'frontier',
}
SOURCES = [
    {'title': 'ML.ENERGY measured open-model inference energy', 'url': 'https://ml.energy/leaderboard/'},
    {'title': 'ML.ENERGY measurement methodology', 'url': 'https://ml.energy/blog/measurement/energy/diagnosing-inference-energy-consumption-with-the-mlenergy-leaderboard-v30/'},
    {'title': 'IEA global electricity CO2 intensity', 'url': 'https://www.iea.org/reports/electricity-2025/emissions'},
    {'title': 'DESNZ 2026 flight conversion methodology', 'url': 'https://assets.publishing.service.gov.uk/media/6a2940543b15d05a7ce3202e/2026-GHG-conversion-factors-methodology-report.pdf'},
]


def estimate(groups, settings=None):
    """groups maps (local date, recorded model) to normalized usage counters."""
    settings = settings or {}
    grid = dict(GRID, **settings.get('grid_kg_co2_per_kwh', {}))
    flight = float(settings.get('flight_tonnes_co2', FLIGHT_TONNES))
    if flight <= 0 or any(not 0 <= grid[s] <= 2 for s in SCENARIOS):
        raise ValueError('Carbon factors require positive flight tonnes and grid factors from 0 to 2.')
    models, days = {}, {}
    def empty():
        return {s: {'kwh': 0., 'tonnes_co2': 0., 'flights': 0.} for s in SCENARIOS}
    totals = empty()
    for (day, model), usage in groups.items():
        count = usage['input'] + usage['output']
        if not count:
            continue
        tier = settings.get('model_profiles', {}).get(model, MODEL_PROFILES.get(model, 'frontier'))
        profile = PROFILES[tier]
        if model not in models:
            models[model] = dict(profile=tier, fallback=model not in MODEL_PROFILES,
                                 actual_parameters=None, proxy=profile['proxy'],
                                 proxy_total_b=profile['total_b'], proxy_active_b=profile['active_b'],
                                 proxy_flops_per_million_fresh_tokens=2 * profile['active_b'] * 1e15,
                                 coefficients={k: dict(zip(SCENARIOS, profile[k])) for k in ('input', 'cached', 'output')},
                                 tokens=0, cached_tokens=0, estimates=empty())
        m = models[model]
        m['tokens'] += count
        m['cached_tokens'] += usage['cached']
        d = days.setdefault(day, empty())
        # Normalized input already includes cache creation; cached reads are a subset.
        fresh = max(0, usage['input'] - usage['cached'])
        for i, scenario in enumerate(SCENARIOS):
            energy = (fresh * profile['input'][i] + usage['cached'] * profile['cached'][i]
                      + usage['output'] * profile['output'][i]) / 1e6
            co2 = energy * grid[scenario] / 1000
            for target in (totals, d, m['estimates']):
                target[scenario]['kwh'] += energy
                target[scenario]['tonnes_co2'] += co2
                target[scenario]['flights'] += co2 / flight
    for m in models.values():
        m['effective_kwh_per_million'] = {s: m['estimates'][s]['kwh'] / m['tokens'] * 1e6 for s in SCENARIOS}
    return dict(totals=totals, days=days, models=models, grid_kg_co2_per_kwh=grid,
                flight_tonnes_co2=flight, sources=SOURCES,
                scope='Operational serving electricity CO2 only; metric tons (1,000 kg).',
                uncertainty='Analyst sensitivity scenarios, not measurements, confidence intervals, or guaranteed bounds.')
