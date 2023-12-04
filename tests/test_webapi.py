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


import asyncio
import datetime as dt
import pytz

import pytest

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from dstclient import *


@pytest.fixture(scope="session")
def cookies():
    """Initialize an API object with cookies."""
    api = WebAPI()
    asyncio.run(api.update_cookies())
    return api._cookies


@pytest.fixture
async def webapi(cookies, engine_none):
    """Create a WebAPI object with or without a database attached to it."""
    if engine_none:
        session = async_sessionmaker(engine_none, expire_on_commit=False)
        async with engine_none.begin() as conn:
            await conn.run_sync(type_registry.metadata.create_all)
        api = WebAPI(session)
    else:
        api = WebAPI()

    api._cookies = cookies
    yield api


async def test_cookies():
    """Test if cookies can be retrieved."""
    api = WebAPI()
    await api.update_cookies()
    assert len(api._cookies) != 0


async def test_get_ticker(webapi: WebAPI):
    """Download basic information about a ticker."""
    ticker = await webapi.get_ticker(ticker_id=1336696633613)
    assert ticker.id == 1336696633613
    assert ticker.published == dt.datetime(2012, 5, 11, 16, 51, tzinfo=pytz.utc)
    assert ticker.title == "RB Salzburg Meister 2012"

    if webapi._db_session:
        async with webapi._db_session() as s, s.begin():
            result = await s.get(Ticker, 1336696633613)
            assert result.title == "RB Salzburg Meister 2012"


async def test_get_ticker_topic_overlap(webapi: WebAPI):
    """Download two tickers with overlapping topics."""
    ta = await webapi.get_ticker(ticker_id=2000134222213)
    tb = await webapi.get_ticker(ticker_id=2000115415698)

    topics_a = set(t.name for t in ta.topics)
    topics_b = set(t.name for t in tb.topics)
    assert set.intersection(topics_a, topics_b)

    if webapi._db_session:
        async with webapi._db_session() as s, s.begin():
            results = (await s.execute(select(Topic))).scalars().all()
            assert len(results) == len(set.union(topics_a, topics_b))


async def test_get_ticker_threads(webapi):
    """Get all threads from an old live ticker."""
    ticker = await webapi.get_ticker(ticker_id=1336696633613)
    threads = await webapi.get_ticker_threads(ticker)
    assert len(threads) == 96

    if webapi._db_session:
        async with webapi._db_session() as s, s.begin():
            results = (await s.execute(select(Thread))).scalars().all()
            assert len(results) == 96


async def test_get_thread_postings(webapi):
    """Get postings of a thread."""
    ticker = await webapi.get_ticker(ticker_id=1336696633613)
    threads = {t.id: t for t in await webapi.get_ticker_threads(ticker)}
    postings = await webapi.get_thread_postings(threads[26066484])
    assert len(postings) == 36

    if webapi._db_session:
        async with webapi._db_session() as s, s.begin():
            results = (await s.execute(select(TickerPosting))).scalars().all()
            assert len(results) == 36


async def test_get_user_full(webapi):
    """Get a user's information."""
    user = await webapi.get_user(legacy_id=228825, relationships=True)
    assert user.id == 228825
    assert user.name == "Winston Smith."

    if webapi._db_session:
        async with webapi._db_session() as s, s.begin():
            results = (await s.execute(select(User))).scalars().all()
            assert len(results) > 100


async def test_get_user_deleted(webapi):
    """Get a user's information."""
    user = await webapi.get_user(legacy_id=738967, relationships=True)
    assert user.id == 738967
    assert user.deleted is not None

    if webapi._db_session:
        async with webapi._db_session() as s, s.begin():
            results = (await s.execute(select(User))).scalars().all()
            assert len(results) == 1


async def test_get_user_deleted_timestamp(webapi):
    """Check if the deleted timestamp in the database stays constant."""
    ua = await webapi.get_user(legacy_id=738967)
    ub = await webapi.get_user(legacy_id=738967)

    if webapi._db_session:
        async with webapi._db_session() as s, s.begin():
            result = (await s.execute(select(User))).scalar()
            assert result.deleted == ua.deleted


@pytest.mark.parametrize(
    "article_id,published,title",
    [
        (
            2429463,
            dt.datetime(2006, 4, 28, 13, 3, tzinfo=pytz.utc),
            "Goldschatz von Nimrud wird wandern",
        ),  # Summer time
        (
            2372424,
            dt.datetime(2006, 3, 17, 15, 43, tzinfo=pytz.utc),
            "Feuer soll Affen weiterentwickelt haben",
        ),  # Winter time
        (
            3000000198057,
            dt.datetime(2023, 12, 4, 6, 8, 37, tzinfo=pytz.utc),
            "Hoffnung auf fallende Zinsen treibt Goldpreis auf Rekordhoch",
        ),
    ],
)
async def test_get_article(webapi, article_id, published, title):
    """Get an article."""
    article = await webapi.get_article(article_id)
    assert article.id == article_id
    assert article.published == published
    assert article.title == title
    assert article.summary is not None
    assert article.content is not None

    if webapi._db_session:
        async with webapi._db_session() as s, s.begin():
            results = (await s.execute(select(Article))).scalars().all()
            assert len(results) == 1


@pytest.mark.parametrize(
    "start_date,end_date,narticles, ntickers",
    [
        (dt.date(1990, 1, 1), dt.date(1990, 1, 31), 0, 0),
        (dt.date(2000, 1, 1), dt.date(2000, 1, 31), 26, 0),
        (dt.date(2020, 3, 1), dt.date(2020, 3, 31), 344, 1),
    ],
)
async def test_get_ressort_entries(webapi, start_date, end_date, narticles, ntickers):
    """Get entries for a ressort."""
    articles, tickers = await webapi.get_ressort_entries(
        "international",
        start_date,
        end_date,
    )
    assert len(articles) == narticles
    assert len(tickers) == ntickers
