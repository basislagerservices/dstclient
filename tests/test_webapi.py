#
# Copyright 2021-2023 Basislager Services
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


import datetime as dt
import pytz

import pytest

from dstclient import DerStandardAPI, DeletedUser, FullUser


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


async def test_get_ticker(api):
    """Get ticker information."""
    ticker = await api.get_ticker(ticker_id=1336696633613)
    assert ticker.id == 1336696633613
    assert ticker.published == dt.datetime(2012, 5, 11, 16, 51, tzinfo=pytz.utc)
    assert ticker.title == "RB Salzburg Meister 2012"


async def test_get_ticker_threads(api):
    """Get all threads from an old live ticker."""
    ticker = await api.get_ticker(ticker_id=1336696633613)
    threads = await api.get_ticker_threads(ticker)
    assert len(threads) == 96


async def test_get_thread_postings(api):
    """Get postings from a thread in an old live ticker."""
    ticker = await api.get_ticker(ticker_id=1336696633613)
    threads = {t.id: t for t in await api.get_ticker_threads(ticker)}
    postings = await api.get_thread_postings(threads[26066484])
    assert len(postings) == 36


async def test_get_user_full(api):
    """Get a user's information."""
    user = await api.get_user(legacy_id=228825)
    assert isinstance(user, FullUser)
    assert user.id == 228825
    assert user.name == "Winston Smith."


async def test_get_user_deleted(api):
    """Get a user's information."""
    user = await api.get_user(legacy_id=738967)
    assert isinstance(user, DeletedUser)
    assert user.id == 738967


@pytest.mark.parametrize(
    "article_id,published",
    [
        (2429463, dt.datetime(2006, 4, 28, 13, 3, tzinfo=pytz.utc)),  # Summer time
        (2372424, dt.datetime(2006, 3, 17, 15, 43, tzinfo=pytz.utc)),  # Winter time
    ],
)
async def test_get_article(api, article_id, published):
    """Get an article."""
    article = await api.get_article(article_id)
    assert article.id == article_id
    assert article.published == published


async def test_contextmanager_api():
    """Fetch a ticker with the context manager API."""
    async with DerStandardAPI() as api:
        ticker = await api.get_ticker(ticker_id=1336696633613)
        threads = {t.id: t for t in await api.get_ticker_threads(ticker)}
        postings = await api.get_thread_postings(threads[26066484])
        assert len(postings) == 36
