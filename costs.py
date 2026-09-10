"""API-equivalent USD at published standard short-context rates, 2026-09-10.
Not invoices: ignores subscriptions, historical rates, long-context/fast premiums,
batch discounts, residency, taxes and tools. Cache writes assume five-minute TTL.
"""
import math
from collections.abc import Mapping
RATES = {
 'claude-fable-5-1': [10,.25,12.5,50], 'claude-fable-5':[10,1,12.5,50],
 'claude-opus-5':[5,.5,6.25,25], 'claude-opus-4-8':[5,.5,6.25,25],
 'claude-sonnet-5':[2,.2,2.5,10], 'claude-haiku-4-5-20251001':[1,.1,1.25,5],
 'gpt-6-astra':[10,1,12.5,50], 'gpt-5.6-sol':[4,.4,5,20],
 'gpt-5.6-terra':[2,.2,2.5,12], 'gpt-5.6-luna':[.2,.02,.25,1.2],
}
SOURCES=['https://platform.claude.com/docs/en/about-claude/pricing','https://developers.openai.com/api/docs/pricing']

def estimate(groups, overrides=None):
    if overrides is not None and not isinstance(overrides,Mapping):
        raise ValueError('cost_rates must be an object mapping model names to four USD rates.')
    rates=dict(RATES)
    for model,values in (overrides or {}).items():
        if not isinstance(values,list) or len(values)!=4 or any(isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) or n<0 for n in values):
            raise ValueError('Cost rates require four finite nonnegative USD numbers: fresh, cached, cache write, output.')
        rates[model]=values
    result=dict(usd=0.,cache_savings_usd=0.,priced_tokens=0,unpriced_tokens=0,models={},days={},sources=SOURCES,rates=rates,as_of='2026-09-10')
    for (day,model),u in groups.items():
        tokens=u['input']+u['output'];rate=rates.get(model)
        m=result['models'].setdefault(model,dict(usd=0.,cache_savings_usd=0.,tokens=0,priced=rate is not None))
        d=result['days'].setdefault(day,dict(usd=0.,unpriced_tokens=0))
        m['tokens']+=tokens
        if rate is None:
            result['unpriced_tokens']+=tokens;d['unpriced_tokens']+=tokens;continue
        cached=min(u['cached'],u['input']);write=min(u.get('cache_write',0),u['input']-cached);fresh=u['input']-cached-write
        usd=(fresh*rate[0]+cached*rate[1]+write*rate[2]+u['output']*rate[3])/1e6
        savings=(cached*(rate[0]-rate[1])+write*(rate[0]-rate[2]))/1e6
        for target in (result,m):target['usd']+=usd;target['cache_savings_usd']+=savings
        d['usd']+=usd;result['priced_tokens']+=tokens
    return result
