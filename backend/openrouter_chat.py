"""Direct, server-side Union Alpha route. No cloud/local silent fallback."""
import os
from pathlib import Path
import httpx
from fastapi import HTTPException

ROUTE = 'openrouter/stealth/union-alpha'
MODEL = 'stealth/union-alpha'


def get_api_key() -> str:
    key = os.environ.get('OPENROUTER_API_KEY', '')
    if not key:
        # Reuse this user's explicitly selected agies profile; never return secrets.
        from dotenv import dotenv_values
        path = Path(os.environ.get('AEGIS_OPENROUTER_ENV_FILE', str(Path.home() / '.hermes/profiles/agies/.env')))
        if path.is_file():
            key = dotenv_values(path).get('OPENROUTER_API_KEY') or ''
    if not key:
        raise HTTPException(503, 'OpenRouter API key is not configured on the server.')
    return key


async def query_openrouter_chat(messages: list) -> tuple[str, str]:
    key = get_api_key()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=10)) as client:
            response = await client.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={'Authorization': f'Bearer {key}'},
                json={'model': MODEL, 'messages': messages, 'stream': False, 'max_tokens': 4096,
                      'provider': {'max_price': {'prompt': 0, 'completion': 0}}},
            )
        if response.status_code != 200:
            raise HTTPException(503, f'OpenRouter Union Alpha unavailable (HTTP {response.status_code}). No fallback was used.')
        data = response.json()
        choices = data.get('choices') or []
        content = ((choices[0].get('message') or {}).get('content') if choices else None)
        if not isinstance(content, str) or not content.strip():
            raise HTTPException(502, 'OpenRouter returned no text completion.')
        return content.strip(), 'openrouter/' + data.get('model', MODEL)
    except httpx.TimeoutException:
        raise HTTPException(504, 'OpenRouter Union Alpha timed out. Try again.') from None
    except httpx.RequestError:
        raise HTTPException(503, 'Could not connect to OpenRouter.') from None
    except (ValueError, TypeError, KeyError):
        raise HTTPException(502, 'OpenRouter returned an invalid response.') from None
