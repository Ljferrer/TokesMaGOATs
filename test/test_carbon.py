import unittest
from carbon import estimate

class CarbonTests(unittest.TestCase):
    def test_phase_accounting_and_unit_conversion(self):
        result = estimate({('2026-09-10','gpt-6-astra'): dict(input=1000000,cached=500000,output=100000)})
        central = result['totals']['central']
        self.assertAlmostEqual(central['kwh'], .41)
        self.assertAlmostEqual(central['tonnes_co2'], .41*.445/1000)
        self.assertAlmostEqual(central['flights'], .41*.445/1000/.27)
        self.assertEqual(result['models']['gpt-6-astra']['actual_parameters'],None)
        self.assertEqual(result['models']['gpt-6-astra']['proxy_flops_per_million_fresh_tokens'],7.4e16)

    def test_cache_is_not_reprocessed_as_fresh_input(self):
        result = estimate({('2026-09-10','unknown'):dict(input=1000000,cached=1000000,output=0)})
        self.assertAlmostEqual(result['totals']['central']['kwh'],.02)
        self.assertTrue(result['models']['unknown']['fallback'])

    def test_daily_and_model_sums_and_scenario_order(self):
        groups={('2026-09-09','claude-sonnet-5'):dict(input=2000,cached=1000,output=100),
                ('2026-09-10','claude-opus-5'):dict(input=3000,cached=1500,output=200)}
        result=estimate(groups)
        for scenario in ('low','central','high'):
            for metric in ('kwh','tonnes_co2','flights'):
                self.assertAlmostEqual(sum(v[scenario][metric] for v in result['days'].values()),result['totals'][scenario][metric])
                self.assertAlmostEqual(sum(v['estimates'][scenario][metric] for v in result['models'].values()),result['totals'][scenario][metric])
        self.assertLess(result['totals']['low']['tonnes_co2'],result['totals']['central']['tonnes_co2'])
        self.assertLess(result['totals']['central']['tonnes_co2'],result['totals']['high']['tonnes_co2'])

    def test_zero_usage_and_assumption_overrides(self):
        self.assertEqual(estimate({})['totals']['central']['tonnes_co2'],0)
        self.assertEqual(estimate({('2026-09-10','<synthetic>'):dict(input=0,cached=0,output=0)})['models'],{})
        result=estimate({('2026-09-10','unknown'):dict(input=1000000,cached=0,output=0)},
                        {'grid_kg_co2_per_kwh':{'central':.1},'flight_tonnes_co2':.5,'model_profiles':{'unknown':'efficient'}})
        self.assertAlmostEqual(result['totals']['central']['tonnes_co2'],.04*.1/1000)
        with self.assertRaises(ValueError):estimate({}, {'flight_tonnes_co2':0})

if __name__=='__main__':unittest.main()
