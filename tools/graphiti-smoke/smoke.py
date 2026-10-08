"""Offline smoke for graphiti-core 0.30.2: import + object construction only.

It makes no network API calls. It uses dummy credentials and unreachable or invalid
endpoints, disables telemetry and constructs the Neo4j driver with no running event
loop, so no index task starts.
"""

import asyncio
import importlib.metadata as md
import json
import os
import sys

os.environ['GRAPHITI_TELEMETRY_ENABLED'] = 'false'
os.environ.pop('OPENAI_API_KEY', None)

result = {'python': sys.version.split()[0], 'versions': {}, 'checks': {}}


def ver(name):
    try:
        return md.version(name)
    except md.PackageNotFoundError:
        return None


for pkg in ('graphiti-core', 'openai', 'httpx', 'httpcore', 'httpx2', 'httpcore2', 'certifi', 'truststore', 'neo4j'):
    result['versions'][pkg] = ver(pkg)


def check(name, fn):
    try:
        out = fn()
        result['checks'][name] = {'ok': True, 'value': out}
    except Exception as e:  # noqa: BLE001
        result['checks'][name] = {'ok': False, 'error': f'{type(e).__name__}: {e}'}


try:
    import graphiti_core  # noqa: F401

    result['checks']['import graphiti_core'] = {'ok': True}
except Exception as e:  # noqa: BLE001
    result['checks']['import graphiti_core'] = {'ok': False, 'error': f'{type(e).__name__}: {e}'}
    print(json.dumps(result, indent=1))
    sys.exit(2)

import openai  # noqa: E402
from openai import AsyncAzureOpenAI, AsyncOpenAI  # noqa: E402

from graphiti_core import Graphiti  # noqa: E402
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient  # noqa: E402
from graphiti_core.embedder.azure_openai import AzureOpenAIEmbedderClient  # noqa: E402
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig  # noqa: E402
from graphiti_core.llm_client import LLMConfig, OpenAIClient  # noqa: E402
from graphiti_core.llm_client.azure_openai_client import AzureOpenAILLMClient  # noqa: E402
from graphiti_core.llm_client.client import is_server_or_retry_error  # noqa: E402
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient  # noqa: E402

cfg = LLMConfig(api_key='sk-dummy-offline', model='gpt-4.1-mini', small_model='gpt-4.1-nano')
objs = {}


def mk_openai_client():
    objs['llm'] = OpenAIClient(config=cfg)
    c = objs['llm'].client
    return f'{type(c).__module__}.{type(c).__name__}; transport={type(c._client).__module__}.{type(c._client).__name__}'


def mk_generic():
    objs['generic'] = OpenAIGenericClient(
        config=LLMConfig(api_key='dummy', base_url='http://127.0.0.1:9/v1', model='local')
    )
    return type(objs['generic']).__name__


def mk_azure():
    az = AsyncAzureOpenAI(
        api_key='dummy', azure_endpoint='https://example.invalid', api_version='2024-10-21'
    )
    objs['azure_llm'] = AzureOpenAILLMClient(azure_client=az, config=cfg)
    objs['azure_emb'] = AzureOpenAIEmbedderClient(azure_client=az, model='text-embedding-3-small')
    return 'AzureOpenAILLMClient+AzureOpenAIEmbedderClient'


def mk_embedder():
    objs['emb'] = OpenAIEmbedder(config=OpenAIEmbedderConfig(api_key='sk-dummy-offline'))
    return type(objs['emb'].client).__name__


def mk_reranker():
    objs['rerank'] = OpenAIRerankerClient(config=cfg)
    return type(objs['rerank']).__name__


def mk_graphiti():
    g = Graphiti(
        'bolt://127.0.0.1:1',
        'neo4j',
        'dummy',
        llm_client=objs['llm'],
        embedder=objs['emb'],
        cross_encoder=objs['rerank'],
    )
    asyncio.run(g.close())
    return 'constructed+closed (no event loop at construction, telemetry disabled)'


def sdk_surface():
    c = AsyncOpenAI(api_key='sk-dummy-offline')
    paths = {
        'responses.parse': lambda: c.responses.parse,
        'chat.completions.create': lambda: c.chat.completions.create,
        'chat.completions.parse': lambda: c.chat.completions.parse,
        'beta.chat.completions.parse': lambda: c.beta.chat.completions.parse,
        'embeddings.create': lambda: c.embeddings.create,
    }
    out = {}
    for k, f in paths.items():
        try:
            f()
            out[k] = True
        except Exception as e:  # noqa: BLE001
            out[k] = f'{type(e).__name__}: {e}'
    for exc in (
        'RateLimitError',
        'LengthFinishReasonError',
        'AuthenticationError',
        'APITimeoutError',
        'APIConnectionError',
        'InternalServerError',
    ):
        out['openai.' + exc] = hasattr(openai, exc)
    from openai.types import EmbeddingModel  # noqa: F401
    from openai.types.chat import ChatCompletionMessageParam  # noqa: F401

    out['types EmbeddingModel/ChatCompletionMessageParam'] = True
    missing = {k: v for k, v in out.items() if v is not True}
    if missing:
        raise AssertionError(f'openai SDK surface missing: {missing}')
    return out


def retry_predicate():
    import httpx

    req = httpx.Request('POST', 'https://example.invalid/v1/x')
    raw_5xx = httpx.HTTPStatusError('x', request=req, response=httpx.Response(503, request=req))
    # What the OpenAI SDK actually raises on a 5xx: openai.InternalServerError, built on the
    # SDK's own transport response type (httpx in 2.x, httpx2 in 3.x).
    try:
        import httpx2 as transport  # type: ignore
    except ImportError:
        transport = httpx
    if ver('openai') and ver('openai').split('.')[0] == '2':
        transport = httpx
    treq = transport.Request('POST', 'https://example.invalid/v1/x')
    sdk_5xx = openai.InternalServerError(
        'server error', response=transport.Response(500, request=treq), body=None
    )
    out = {
        'httpx.HTTPStatusError(503) retried': is_server_or_retry_error(raw_5xx),
        'openai.InternalServerError(500) retried by base predicate': is_server_or_retry_error(
            sdk_5xx
        ),
        'sdk response family': transport.__name__,
    }
    # graphiti's only use of httpx: its base predicate retries a raw httpx 5xx. The SDK-500 value
    # is recorded, not asserted.
    if out['httpx.HTTPStatusError(503) retried'] is not True:
        raise AssertionError(f'base retry predicate no longer retries a raw httpx 503: {out}')
    return out


check('OpenAIClient', mk_openai_client)
check('OpenAIGenericClient', mk_generic)
check('Azure clients', mk_azure)
check('OpenAIEmbedder', mk_embedder)
check('OpenAIRerankerClient', mk_reranker)
check('Graphiti(neo4j uri, injected clients)', mk_graphiti)
check('openai SDK surface used by graphiti', sdk_surface)
check('retry predicate', retry_predicate)

print(json.dumps(result, indent=1))
sys.exit(0 if all(v.get('ok') for v in result['checks'].values()) else 1)
