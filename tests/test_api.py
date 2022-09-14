#
# Copyright 2021-2022 Basislager Services
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#

"""Tests for the dstclient.api module."""


import asyncio

import pytest

from dstclient import DerStandardAPI


@pytest.fixture(scope="module")
def api():
    """Initialize an API object with cookies."""
    api = DerStandardAPI()
    asyncio.run(api.update_cookies())

    return api


async def test_cookies():
    """Test if cookies can be retrieved."""
    api = DerStandardAPI()
    await api.update_cookies()
    assert len(api._cookies) != 0


@pytest.mark.skip(reason="fails because of caching?")
async def test_cookies_update():
    """Test if cookies can be retrieved multiple times."""
    api = DerStandardAPI()
    await api.update_cookies()
    first = api._cookies
    await api.update_cookies()
    second = api._cookies
    assert first != second


async def test_get_ticker_threads(api):
    """Get all threads from an old live ticker."""
    threads = await api.get_ticker_threads(ticker_id=1336696633613)
    assert len(threads) == 96


async def test_get_thread_postings(api):
    """Get postings from a thread in an old live ticker."""
    threads = await api.get_thread_postings(ticker_id=1336696633613, thread_id=26065423)
    assert len(threads) == 8


async def test_get_ticker_threads_with_session(api, mocker):
    """Get all threads from an old live ticker."""
    async with api.session() as session:
        smock = mocker.patch("dstclient.api.ClientSession")
        threads = await api.get_ticker_threads(
            ticker_id=1336696633613,
            client_session=session,
        )
        assert smock.call_count == 0
    assert len(threads) == 96


async def test_get_thread_postings_with_session(api, mocker):
    """Get postings from a thread in an old live ticker."""
    async with api.session() as session:
        smock = mocker.patch("dstclient.api.ClientSession")
        threads = await api.get_thread_postings(
            ticker_id=1336696633613,
            thread_id=26065423,
            client_session=session,
        )
        assert smock.call_count == 0
    assert len(threads) == 8


@pytest.mark.parametrize(
    "article_id,forum_id",
    [
        (2000139096060, "2ElFnh4hoV9qyILJHCCYxeUfE4u"),
        (2000139105349, "2ElgqjRTEjnrQxkrdI4HaSlEakw"),
        (2000139053504, "2EiAs5HlM0bGW0ZjGiqThlt5GTF"),
        (2000139100674, "2ElPpBr7oBIcUl6VJoJmaLRDeLX"),
        (2000139091832, "2El4k6eHDupOjBkhZMfJrTjaDBE"),
        (2000139107626, "2Em01E9pMuCTnoXp9q1XTUkAqq9"),
        (2000139101229, "2ElRS6ZEnfC0sQqJ488bhH57tru"),
        (2000139026342, "2EfeS5M2EMYxhabZxWAInR54jj7"),
        (2000139082527, "2EkfUzrb4O4n53dlIAz1MhhdJzA"),
        (2000139089058, "2EkvRGx7uPGznqMYHPTy7RJUT87"),
        (2000139070622, "2EigzOL0m9qWOPcWIdQw5AlOUEh"),
        (2000139068548, "2EidcaHYqtXRWluleSC37JYdfgs"),
        (2000139081230, "2EkbNXADsP55O0jxMBL2zxrwbg3"),
        (2000139091383, "2El37dlR0iHjDhG6HCdAamyEylo"),
        (2000139101643, "2ElT8F6iMYI06cY8bOSZnW2tQqO"),
    ],
)
async def test_get_forum_id(api, article_id, forum_id):
    """Get the GraphQL ID of a forum."""
    result = await api._get_forum_id(article_id)
    assert result == forum_id
