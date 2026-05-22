import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

from app import (
    MARKET_SCAN_AUTO_REFRESH_STRATEGIES,
    app,
    get_market_scan_async_response,
    get_market_scan_cache_key,
    get_market_scan_entry,
    market_scan_cache,
    store_market_scan_entry,
    trigger_market_scan_auto_refresh,
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

    @patch('app.start_market_scan_refresh', return_value=True)
    @patch('app.is_trading_day', return_value=True)
    def test_after_close_auto_refresh_starts_all_market_strategies(self, _mock_trading_day, mock_start_refresh):
        now = datetime(2026, 5, 19, 15, 5)

        started = trigger_market_scan_auto_refresh(now=now)

        self.assertEqual(started, len(MARKET_SCAN_AUTO_REFRESH_STRATEGIES))
        self.assertEqual(mock_start_refresh.call_count, len(MARKET_SCAN_AUTO_REFRESH_STRATEGIES))
        self.assertEqual(
            [call.args[0] for call in mock_start_refresh.call_args_list],
            list(MARKET_SCAN_AUTO_REFRESH_STRATEGIES),
        )

        for call in mock_start_refresh.call_args_list:
            self.assertTrue(call.kwargs['force_refresh'])
            self.assertEqual(call.kwargs['trigger_source'], 'scheduled')
            self.assertEqual(call.kwargs['current_time'], now)

    @patch('app.start_market_scan_refresh')
    @patch('app.is_trading_day', return_value=True)
    def test_before_close_auto_refresh_does_not_start_refresh(self, _mock_trading_day, mock_start_refresh):
        started = trigger_market_scan_auto_refresh(now=datetime(2026, 5, 19, 14, 59))

        self.assertEqual(started, 0)
        mock_start_refresh.assert_not_called()

    def test_market_scan_cache_reads_shared_snapshot_from_disk(self):
        requested_strategy = '箱体突破'
        cache_key = get_market_scan_cache_key(requested_strategy)
        entry = {
            'strategy': requested_strategy,
            'data': [{'代码': '600000', '策略': requested_strategy}],
            'count': 1,
            'scanned_count': 8,
            'timestamp': datetime.now().isoformat(),
            'refreshing': False,
            'error': None,
        }

        with tempfile.TemporaryDirectory() as cache_dir:
            with patch.dict(os.environ, {'MARKET_SCAN_CACHE_DIR': cache_dir}, clear=False):
                store_market_scan_entry(cache_key, entry)
                market_scan_cache.clear()

                loaded = get_market_scan_entry(cache_key)

        self.assertEqual(loaded['strategy'], requested_strategy)
        self.assertEqual(loaded['count'], 1)
        self.assertEqual(loaded['data'][0]['策略'], requested_strategy)


if __name__ == '__main__':
    unittest.main()
