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


import datetime as dt

import pytest

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import event

from dstclient.types import *


async def test_create_user(empty_session, fullusergen, delusergen):
    """Create a new user, insert it and read it back."""
    user = fullusergen()
    deluser = delusergen()
    async with empty_session() as session, session.begin():
        session.add(user)
        session.add(deluser)

    async with empty_session() as session, session.begin():
        result = await session.get(User, user.id)
        assert result.id == user.id
        assert result.name == user.name

        result = await session.get(User, deluser.id)
        assert result.id == deluser.id
        assert result.deleted is not None


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


async def test_update_ticker_threads(empty_session, tickergen, threadgen):
    """Create multiple threads in the same ticker and read them back."""
    ticker = tickergen()
    threads = [threadgen(ticker=ticker) for _ in range(8)]
    async with empty_session() as session, session.begin():
        session.add_all(threads)

    async with empty_session() as session, session.begin():
        result = await session.get(Ticker, ticker.id)
        await session.refresh(result, attribute_names=["threads"])
        assert {t.id for t in result.threads} == {t.id for t in threads}


async def test_append_ticker_threads(empty_session, tickergen, threadgen):
    """Append threads through the backref of the ticker."""
    ticker = tickergen()
    threads = [threadgen(ticker=ticker) for _ in range(8)]
    async with empty_session() as session, session.begin():
        session.add(ticker)
        ticker.threads.extend(threads)

    async with empty_session() as session, session.begin():
        result = await session.get(Ticker, ticker.id)
        await session.refresh(result, attribute_names=["threads"])
        assert {t.id for t in result.threads} == {t.id for t in threads}


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


async def test_tickerposting_responses(empty_session, tickerpostinggen):
    """Create a tickerposting with responses and read them back."""
    parent = tickerpostinggen()
    children = [tickerpostinggen(parent=parent) for _ in range(8)]
    async with empty_session() as session, session.begin():
        session.add(parent)
        session.add_all(children)

    async with empty_session() as session, session.begin():
        result = await session.get(TickerPosting, parent.id)
        await session.refresh(result, attribute_names=["responses"])
        assert len(result.responses) == 8


async def test_tickerposting_wrong_thread(empty_session, tickerpostinggen, threadgen):
    """Create a response with the wrong thread."""
    parent = tickerpostinggen()
    child = tickerpostinggen(parent=parent)

    with pytest.raises(ValueError) as excinfo:
        child.thread = threadgen()
    assert "parent posting is in a different thread" in str(excinfo.value)

    # This should not raise, because it constructs a regular top-level posting,
    # although in a strange manner.
    child.parent = None
    child.thread = threadgen()


async def test_followers(empty_session, fullusergen):
    """Create users and let them follow each other."""
    users = [fullusergen() for _ in range(32)]

    # User with index i follows i + 1 to i + 3
    for i, user in enumerate(users):
        user.followees.add(users[(i + 1) % len(users)])
        user.followees.add(users[(i + 2) % len(users)])
        user.followees.add(users[(i + 3) % len(users)])

    for user in users:
        assert len(user.followers) == 3

    async with empty_session() as session, session.begin():
        session.add_all(users)
        for user in users:
            result = await session.get(User, user.id)
            assert user == result
            assert len(result.followers) == 3
            assert len(result.followees) == 3
