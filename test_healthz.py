import unittest

from app import app


class HealthzEndpointTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_healthz_returns_expected_shape(self):
        response = self.client.get('/healthz')
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['status'], 'ok')
        self.assertEqual(payload['service'], 'quant-ai')
        self.assertIn('version', payload)
        self.assertIn('time', payload)


if __name__ == '__main__':
    unittest.main()
