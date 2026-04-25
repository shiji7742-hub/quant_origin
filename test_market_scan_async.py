import unittest
from datetime import datetime

from app import (
    app,
    get_market_scan_async_response,
    get_market_scan_cache_key,
    market_scan_cache,
)


class MarketScanAsyncResponseTests(unittest.TestCase):
    def setUp(self):
        market_scan_cache.clear()

    def tearDown(self):
        market_scan_cache.clear()

    def test_async_scan_filters_cached_rows_from_other_strategy(self):
        requested_strategy = '涨停破位洗盘'
        cache_key = get_market_scan_cache_key(requested_strategy)

        market_scan_cache[cache_key] = {
            'strategy': requested_strategy,
            'data': [
                {
                    '代码': '000592',
                    '最新价': 12.57,
                    '涨跌幅': 4.58,
                    '策略': '均线粘合发散',
                    '说明': '均线粘合发散（3/3条件）',
                }
            ],
            'count': 1,
            'scanned_count': 5,
            'timestamp': datetime.now().isoformat(),
            'refreshing': False,
            'error': None,
        }

        with app.test_request_context('/api/scan?strategy=涨停破位洗盘&async=1'):
            response = get_market_scan_async_response(requested_strategy)

        payload = response.get_json()

        self.assertTrue(payload['success'])
        self.assertEqual(payload['strategy'], requested_strategy)
        self.assertEqual(payload['data'], [])
        self.assertEqual(payload['count'], 0)

    def test_async_scan_keeps_cached_rows_for_requested_strategy(self):
        requested_strategy = '涨停破位洗盘'
        cache_key = get_market_scan_cache_key(requested_strategy)

        market_scan_cache[cache_key] = {
            'strategy': requested_strategy,
            'data': [
                {
                    '代码': '600487',
                    '最新价': 53.39,
                    '涨跌幅': 2.75,
                    '策略': requested_strategy,
                    '说明': '涨停破位洗盘（宽松版）',
                }
            ],
            'count': 1,
            'scanned_count': 5,
            'timestamp': datetime.now().isoformat(),
            'refreshing': False,
            'error': None,
        }

        with app.test_request_context('/api/scan?strategy=涨停破位洗盘&async=1'):
            response = get_market_scan_async_response(requested_strategy)

        payload = response.get_json()

        self.assertTrue(payload['success'])
        self.assertEqual(payload['strategy'], requested_strategy)
        self.assertEqual(len(payload['data']), 1)
        self.assertEqual(payload['data'][0]['策略'], requested_strategy)
        self.assertEqual(payload['count'], 1)


if __name__ == '__main__':
    unittest.main()
