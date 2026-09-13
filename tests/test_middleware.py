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


if __name__ == "__main__":
    unittest.main()
