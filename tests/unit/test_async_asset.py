"""Tests for AsyncAsset (async asset I/O).

Data accessors are shared with the sync Asset via _AssetBase and covered in
test_asset.py; these focus on the async I/O methods and the async did_url.
"""

from __future__ import annotations

import pytest

from covia.async_api.asset import AsyncAsset
from covia.async_api.job import AsyncJob
from tests.conftest import VENUE_URL

API_BASE = f"{VENUE_URL}/api/v1/"


class TestAsyncAssetData:
    def test_shared_data_accessors(self):
        asset = AsyncAsset({"name": "Foo", "operation": {}}, id="abc")
        assert asset.name == "Foo"
        assert asset.is_operation
        assert asset.id == "abc"

    def test_repr(self):
        assert repr(AsyncAsset({"name": "Foo"})) == "AsyncAsset('Foo')"


class TestAsyncAssetContent:
    async def test_get_content(self, httpx_mock, async_venue):
        httpx_mock.add_response(url=f"{API_BASE}assets/abc123/content", content=b"file data")
        asset = AsyncAsset({}, id="abc123", venue=async_venue)
        assert await asset.get_content() == b"file data"

    async def test_get_content_no_venue_raises(self):
        asset = AsyncAsset({}, id="abc123")
        with pytest.raises(ValueError, match="no attached venue"):
            await asset.get_content()

    async def test_put_content(self, httpx_mock, async_venue):
        httpx_mock.add_response(url=f"{API_BASE}assets/abc123/content", text='"hash123"')
        asset = AsyncAsset({}, id="abc123", venue=async_venue)
        assert await asset.put_content(b"new data") == "hash123"


class TestAsyncAssetInvoke:
    async def test_run(self, httpx_mock, async_venue):
        httpx_mock.add_response(
            url=f"{API_BASE}invoke",
            json={"id": "job001", "status": "COMPLETE", "output": 99},
            status_code=201,
        )
        asset = AsyncAsset({"operation": {}}, id="abc123", venue=async_venue)
        assert await asset.run({"x": 1}) == 99

    async def test_invoke_returns_async_job(self, httpx_mock, async_venue):
        httpx_mock.add_response(
            url=f"{API_BASE}invoke",
            json={"id": "job001", "status": "COMPLETE", "output": "r"},
            status_code=201,
        )
        asset = AsyncAsset({"operation": {}}, id="abc123", venue=async_venue)
        job = await asset.invoke({"x": 1})
        assert isinstance(job, AsyncJob)
        assert job.is_complete

    async def test_run_no_venue_raises(self):
        asset = AsyncAsset({"operation": {}}, id="abc123")
        with pytest.raises(ValueError, match="no attached venue"):
            await asset.run()


class TestAsyncAssetDidUrl:
    async def test_did_url(self, httpx_mock, async_venue):
        httpx_mock.add_response(
            url=f"{VENUE_URL}/.well-known/did.json",
            json={"id": "did:web:test.covia.ai"},
        )
        asset = AsyncAsset({}, id="abc123", venue=async_venue)
        assert await asset.did_url() == "did:web:test.covia.ai/a/abc123"

    async def test_did_url_without_venue(self):
        asset = AsyncAsset({}, id="abc123")
        assert await asset.did_url() is None
