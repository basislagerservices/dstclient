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

"""Tests for the database types."""


import pytest

from sqlalchemy.exc import IntegrityError

from dstclient.types import *


async def test_create_user(empty_session, fullusergen, delusergen):
    """Create a new user, insert it and read it back."""
    user = fullusergen()
    deluser = delusergen()
    async with empty_session() as session, session.begin():
        session.add(user)
        session.add(deluser)

    async with empty_session() as session, session.begin():
        result = await session.get(FullUser, user.id)
        assert result.id == user.id
        assert result.name == user.name

        result = await session.get(DeletedUser, deluser.id)
        assert result.id == deluser.id


async def test_create_ticker(empty_session, tickergen):
    """Create a ticker and read it back."""
    ticker = tickergen()
    async with empty_session() as session, session.begin():
        session.add(ticker)

    async with empty_session() as session, session.begin():
        result = await session.get(Ticker, ticker.id)

        assert result.id == ticker.id
        assert result.published == ticker.published


async def test_create_thread(empty_session, threadgen):
    """Create a thread and read it back."""
    thread = threadgen()
    async with empty_session() as session, session.begin():
        session.add(thread)

    async with empty_session() as session, session.begin():
        result = await session.get(Thread, thread.id)

        assert result.id == thread.id
        assert result.published == thread.published
        assert result.ticker.id == thread.ticker.id
        assert result.ticker_id == thread.ticker_id
        assert result.user.id == thread.user.id
        assert result.user_id == thread.user_id
        assert result.upvotes == thread.upvotes
        assert result.downvotes == thread.downvotes
        assert result.title == thread.title
        assert result.message == thread.message


async def test_create_thread_userid(empty_session, threadgen, fullusergen):
    """Create a thread with an existing numerical user ID and read it back."""
    user = fullusergen()
    thread = threadgen(user=user.id)

    async with empty_session() as session, session.begin():
        session.add(user)
        session.add(thread)

    async with empty_session() as session, session.begin():
        result = await session.get(Thread, thread.id)

        assert result.user_id == user.id
        assert result.user.id == user.id


async def test_create_thread_userid_error(empty_session, threadgen):
    """Adding a thread with a made up user ID should create an error."""
    thread = threadgen(user=42)

    with pytest.raises(IntegrityError) as excinfo:
        async with empty_session() as session, session.begin():
            session.add(thread)

    assert "FOREIGN KEY" in str(excinfo.value)


async def test_create_thread_tickerid(empty_session, threadgen, tickergen):
    """Create a thread with an existing numerical ticker ID and read it back."""
    ticker = tickergen()
    thread = threadgen(ticker=ticker.id)

    async with empty_session() as session, session.begin():
        session.add(ticker)
        session.add(thread)

    async with empty_session() as session, session.begin():
        result = await session.get(Thread, thread.id)

        assert result.ticker_id == ticker.id
        assert result.ticker.id == ticker.id


async def test_create_thread_tickerid_error(empty_session, threadgen):
    """Adding a thread with a made up ticker ID should create an error."""
    thread = threadgen(ticker=42)

    with pytest.raises(IntegrityError) as excinfo:
        async with empty_session() as session, session.begin():
            session.add(thread)

    assert "FOREIGN KEY" in str(excinfo.value)


async def test_create_tickerposting(empty_session, tickerpostinggen):
    """Create a ticker posting and read it back."""
    posting = tickerpostinggen()
    async with empty_session() as session, session.begin():
        session.add(posting)

    async with empty_session() as session, session.begin():
        result = await session.get(TickerPosting, posting.id)
        assert result is not None
        result = await session.get(Posting, posting.id)
        assert result is not None