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

"""Tests for the unified API."""


import datetime as dt

import pytest

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from dstclient import *


@pytest.fixture
async def api(engine):
    """Unified API with a database pre-filled with dummy data.

    Ticker-i
    +--- Thread-0
         +--- Posting-0
         ...
         +--- Posting-(N-1)
    ...
    +--- Thread-(N-1)
         +--- Posting-0
         ...
         +--- Posting-(N-1)
    """

    def usergen(i: int) -> User:
        return User(
            id=i,
            member_id=f"member-id-{i}",
            name=f"user-{i}",
            registered=dt.datetime(1970, 1, 1) + dt.timedelta(days=i),
        )

    def tickergen(i: int) -> Ticker:
        return Ticker(
            id=1000000 * i,
            title=f"Title-{i}",
            published=dt.datetime(1970, 1, 1) + dt.timedelta(days=i),
            topics=[],
        )

    def threadgen(ticker: Ticker, user: User, i: int) -> Thread:
        return Thread(
            id=ticker.id + 1000 * i,
            published=dt.datetime(1970, 1, 1) + dt.timedelta(days=i),
            ticker=ticker,
            user=user,
            upvotes=0,
            downvotes=0,
            title=f"THREAD-{i}",
            message=f"MESSAGE-{i}",
        )

    def postinggen(thread: Thread, user: User, i: int) -> TickerPosting:
        return TickerPosting(
            id=thread.id + i,
            user=user,
            parent=None,
            published=dt.datetime(1970, 1, 1) + dt.timedelta(days=i),
            upvotes=0,
            downvotes=0,
            title=f"POSTING-{i}",
            message=f"MESSAGE-{i}",
            thread=thread,
        )

    N = 8
    session = async_sessionmaker(engine, expire_on_commit=False)
    async with session() as s, s.begin():
        users = [usergen(i) for i in range(N)]
        s.add_all(users)
        for ticker_id in range(N):
            ticker = tickergen(ticker_id)
            s.add(ticker)
            for thread_id in range(N):
                thread = threadgen(ticker, users[thread_id], thread_id)
                s.add(thread)
                for posting_id in range(N):
                    posting = postinggen(thread, users[posting_id], posting_id)
                    s.add(posting)

    yield DerStandardAPI(engine)


async def test_database_readonly(api: DerStandardAPI):
    """Check that access to the database is readonly."""
    # Get a user and change its name.
    async with api.db() as s:
        user = await s.get(User, 0)
        user.name = "FOOBAR"

    # Get the same user and check if the name was changed.
    async with api.db() as s:
        user = await s.get(User, 0)
        assert user.name != "FOOBAR"
