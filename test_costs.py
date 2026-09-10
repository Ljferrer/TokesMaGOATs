import unittest
from costs import estimate

class CostTests(unittest.TestCase):
    def test_cache_partition_and_savings(self):
        x=estimate({('2026-09-10','claude-opus-5'):dict(input=1000000,cached=600000,cache_write=100000,output=100000)})
        self.assertAlmostEqual(x['usd'],4.925)
        self.assertAlmostEqual(x['cache_savings_usd'],2.575)
        self.assertEqual(x['priced_tokens'],1100000)
    def test_unknown_is_unpriced(self):
        x=estimate({('2026-09-10','unknown'):dict(input=100,cached=0,output=20)})
        self.assertEqual(x['unpriced_tokens'],120)
        self.assertFalse(x['models']['unknown']['priced'])
    def test_overrides_and_invalid_rates(self):
        for value in ([1,2,3], [1,2,3,float('nan')], [1,2,3,-1]):
            with self.assertRaises(ValueError):estimate({}, {'custom':value})
        x=estimate({('2026-09-10','custom'):dict(input=1000000,cached=0,output=0)}, {'custom':[2,1,2,3]})
        self.assertEqual(x['usd'],2)
    def test_non_object_rate_settings(self):
        for value in ([1],[], 'rates', '', 1, 0, True, False):
            with self.assertRaisesRegex(ValueError,'cost_rates must be an object'):
                estimate({},value)
