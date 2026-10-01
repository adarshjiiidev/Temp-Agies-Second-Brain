"""Mocked transport tests; live browser verification is separate."""
import unittest
from unittest.mock import patch
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import httpx
from fastapi import HTTPException
from backend.openrouter_chat import query_openrouter_chat

class OpenRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_payload_and_model(self):
        async def respond(request):
            import json
            payload = json.loads(request.content)
            self.assertEqual(payload['model'], 'stealth/union-alpha')
            self.assertEqual(request.headers['authorization'], 'Bearer test-only')
            return httpx.Response(200, json={'model':'stealth/union-alpha','choices':[{'message':{'content':'OK'}}]})
        client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        with patch('backend.openrouter_chat.get_api_key', return_value='test-only'), patch('backend.openrouter_chat.httpx.AsyncClient', return_value=client):
            self.assertEqual(await query_openrouter_chat([{'role':'user','content':'Hi'}]), ('OK', 'openrouter/stealth/union-alpha'))

    async def test_provider_failure_is_not_success_text(self):
        client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(429, text='sensitive provider body')))
        with patch('backend.openrouter_chat.get_api_key', return_value='test-only'), patch('backend.openrouter_chat.httpx.AsyncClient', return_value=client):
            with self.assertRaises(HTTPException) as caught:
                await query_openrouter_chat([])
            self.assertEqual(caught.exception.status_code, 503)
            self.assertNotIn('sensitive', caught.exception.detail)


if __name__ == '__main__':
    unittest.main()
