"""
Unit tests for middleware pipeline and rate limiting.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from middleware import MiddlewarePipeline, RateLimiter, RequestContext


class TestMiddleware(unittest.TestCase):
    def test_rate_limiter_allowed(self):
        limiter = RateLimiter(max_requests=5, window_seconds=10)
        for _ in range(5):
            self.assertTrue(limiter.is_allowed("client-1"))
        self.assertFalse(limiter.is_allowed("client-1"))
        # Different client should still be allowed
        self.assertTrue(limiter.is_allowed("client-2"))

    def test_middleware_pipeline_pass(self):
        pipeline = MiddlewarePipeline()
        ctx = RequestContext(endpoint="/items", token="valid-token")
        err = pipeline.process_request(ctx)
        self.assertIsNone(err)

    def test_middleware_pipeline_rate_limit(self):
        pipeline = MiddlewarePipeline()
        pipeline.rate_limiter = RateLimiter(max_requests=2, window_seconds=10)
        ctx = RequestContext(endpoint="/items", token="flood-token")
        
        self.assertIsNone(pipeline.process_request(ctx))
        self.assertIsNone(pipeline.process_request(ctx))
        
        blocked = pipeline.process_request(ctx)
        self.assertIsNotNone(blocked)
        self.assertEqual(blocked["status_code"], 429)

    def test_rate_limiter_configure_and_reset(self):
        limiter = RateLimiter(max_requests=2, window_seconds=10)
        self.assertTrue(limiter.is_allowed("user-1"))
        self.assertTrue(limiter.is_allowed("user-1"))
        self.assertFalse(limiter.is_allowed("user-1"))

        # Configure to allow more requests
        limiter.configure(max_requests=5, window_seconds=20)
        self.assertEqual(limiter.max_requests, 5)
        self.assertEqual(limiter.window_seconds, 20)
        self.assertTrue(limiter.is_allowed("user-1"))

        # Reset specific user
        self.assertTrue(limiter.reset("user-1"))
        self.assertEqual(len(limiter._history.get("user-1", [])), 0)

        # Reset all
        limiter.is_allowed("user-2")
        self.assertTrue(limiter.reset())
        self.assertEqual(len(limiter._history), 0)

    def test_rate_limiter_stats_and_pipeline_info(self):
        pipeline = MiddlewarePipeline()
        pipeline.rate_limiter.is_allowed("client-alpha")
        pipeline.rate_limiter.is_allowed("client-beta")

        stats = pipeline.rate_limiter.get_stats()
        self.assertEqual(stats["max_requests"], 100)
        self.assertEqual(stats["window_seconds"], 60)
        self.assertEqual(stats["active_clients_count"], 2)
        self.assertEqual(stats["total_tracked_requests"], 2)

        info = pipeline.get_pipeline_info()
        self.assertTrue(info["pipeline_enabled"])
        self.assertIn("rate_limiter", info)


if __name__ == "__main__":
    unittest.main()

