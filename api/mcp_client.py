"""
SellerSprite MCP client — Claude'suz, doğrudan backend'den bağlanır.

Bağlantı testinde (Claude Desktop üzerinden) doğrulanmış gerçek tool adları
ve davranışlar burada sabittir. Yeni bir tool eklerken önce Claude'da
tool_search ile test edip gerçek parametre/çıktı şemasını doğrula, sonra
buraya ekle — tahmin yürütme.

KRİTİK BULGU: returnFields parametresi güvenilir değil (null döndürüyor).
Bu yüzden hiçbir çağrıda returnFields KULLANMIYORUZ — tam objeyi çekip
Python tarafında filtreliyoruz.
"""
import os
import json
from contextlib import asynccontextmanager
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

SELLERSPRITE_SECRET_KEY = os.environ["SELLERSPRITE_SECRET_KEY"]
MCP_URL = f"https://mcp.sellersprite.com/mcp?secret-key={SELLERSPRITE_SECRET_KEY}"


@asynccontextmanager
async def mcp_session():
    """Her istek için kısa ömürlü bir MCP oturumu açar."""
    async with streamablehttp_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def call_tool(tool_name: str, arguments: dict) -> dict:
    """
    Tek bir SellerSprite MCP tool'unu çağırır, JSON içeriğini döndürür.
    returnFields ASLA gönderilmez (bkz. modül docstring'i).
    """
    arguments = {k: v for k, v in arguments.items() if k != "returnFields"}
    async with mcp_session() as session:
        result = await session.call_tool(tool_name, arguments)
        # MCP tool sonucu content bloklarından oluşur; ilk text bloğunu al
        for block in result.content:
            if hasattr(block, "text"):
                try:
                    return json.loads(block.text)
                except json.JSONDecodeError:
                    return {"raw": block.text}
        return {}


async def call_many(calls: list[tuple[str, dict]]) -> list[dict]:
    """
    Birden fazla tool çağrısını sıralı çalıştırır (aynı oturum içinde,
    bağlantı kurma maliyetini tekrarlamamak için).
    calls: [(tool_name, arguments), ...]
    """
    results = []
    async with mcp_session() as session:
        for tool_name, arguments in calls:
            arguments = {k: v for k, v in arguments.items() if k != "returnFields"}
            result = await session.call_tool(tool_name, arguments)
            parsed = {}
            for block in result.content:
                if hasattr(block, "text"):
                    try:
                        parsed = json.loads(block.text)
                    except json.JSONDecodeError:
                        parsed = {"raw": block.text}
                    break
            results.append(parsed)
    return results
