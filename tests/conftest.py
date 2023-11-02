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

"""Configuration and fixtures for unit tests."""

import datetime as dt
import random
import string
from typing import Union

from lorem_text import lorem

import pytest

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from dstclient.types import (
    type_registry,
    User,
    Ticker,
    Thread,
    TickerPosting,
    FullUser,
    DeletedUser,
)


def random_str(k: int) -> str:
    """Create a random string."""
    return "".join(random.choices(string.ascii_letters, k=k))


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set the foreign_key pragma to check for nonexisting foreign keys."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
async def empty_session(tmp_path):
    """Create an empty database with initialized tables.

    The result is the session factory.
    """
    engine = create_async_engine(f"sqlite+aiosqlite:////{tmp_path}/db.sql")
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(type_registry.metadata.drop_all)
        await conn.run_sync(type_registry.metadata.create_all)

    yield async_session

    await engine.dispose()


@pytest.fixture
async def fullusergen():
    """Create a random full user."""

    def factory() -> FullUser:
        name = random_str(16)
        id = random.randrange(2**32)
        member_id = random_str(27)
        registered = dt.datetime.fromtimestamp(random.randrange(2**32)).date()
        user = FullUser(id, member_id, name, registered)
        return user

    return factory


@pytest.fixture
async def delusergen():
    """Create a random deleted user."""

    def factory() -> DeletedUser:
        return DeletedUser(random.randrange(2**32))

    return factory


@pytest.fixture
async def tickergen():
    """Create a random ticker."""

    def factory() -> Ticker:
        id = random.randrange(2**32)
        published = dt.datetime.fromtimestamp(random.randrange(2**32))
        return Ticker(id, random_str(32), published)

    return factory


@pytest.fixture
async def threadgen(fullusergen, tickergen):
    """Create a random thread."""

    def factory(
        ticker: Union[None, int, Ticker] = None, user: Union[None, int, User] = None
    ) -> Thread:
        id = random.randrange(2**32)
        published = dt.datetime.fromtimestamp(random.randrange(2**32))
        if ticker is None:
            ticker = tickergen()
        if user is None:
            user = fullusergen()

        up = random.randrange(2**10)
        down = random.randrange(2**10)
        title = random.choice([None, random_str(16)])
        message = random.choice([None, lorem.sentence()])

        return Thread(
            id=id,
            published=published,
            ticker=ticker,
            user=user,
            upvotes=up,
            downvotes=down,
            title=title,
            message=message,
        )

    return factory


@pytest.fixture
async def tickerpostinggen(fullusergen, threadgen):
    """Create a random ticker posting."""

    def factory(
        thread: Union[None, int, Thread] = None,
        user: Union[None, int, User] = None,
        parent: Union[None, TickerPosting] = None,
    ) -> TickerPosting:
        if user is None:
            user = fullusergen()

        if thread is None and parent is None:
            thread = threadgen()
            parent = None
        elif thread is None and parent is not None:
            thread = parent.thread
            parent = parent
        elif thread is not None and parent is None:
            thread = thread
            parent = None
        else:
            assert False, "Invalid combination of parent and thread"

        id = random.randrange(2**32)
        published = dt.datetime.fromtimestamp(random.randrange(2**32))

        return TickerPosting(
            id=id,
            user=user,
            parent=parent,
            published=published,
            upvotes=random.randrange(2**10),
            downvotes=random.randrange(2**10),
            title=random.choice([None, random_str(16)]),
            message=random.choice([None, lorem.sentence()]),
            thread=thread,
        )

    return factory
