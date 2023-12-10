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

"""Tests for database types."""


import datetime as dt

import pytest

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from dstclient import *


@pytest.fixture
def zero_object():
    """Create an instance of a type with all IDs set to 0."""
    ts = dt.datetime.utcnow().replace(microsecond=0)
    generators = {
        User: lambda: User(0, deleted=ts),
        Ticker: lambda: Ticker(0, None, title=None, published=ts, topics=[]),
        Thread: lambda: Thread(0, None, ts, 0, 0, 0, 0, None, None),
        TickerPosting: lambda: TickerPosting(0, None, 0, None, ts, 0, 0, None, None, 0),
        Article: lambda: Article(0, None, ts, None, None, None, []),
        ArticlePosting: lambda: ArticlePosting(
            0, None, 0, None, ts, 0, 0, None, None, 0
        ),
    }

    def factory(cls):
        return generators[cls]()

    return factory


@pytest.mark.parametrize(
    "objtypes",
    [
        (User,),
        (Ticker,),
        (User, Ticker, Thread),
        (User, Ticker, Thread, TickerPosting),
        (Article,),
        (User, Article, ArticlePosting),
    ],
)
async def test_add_id_zero(
    empty_session: async_sessionmaker[AsyncSession],
    objtypes: tuple[str, ...],
    zero_object,
):
    """Add objects with ID set to 0 while satisfying foreign key constraints.

    This could cause problems with MySQL because auto-increment would choose a
    automatic ID not only when the ID is NULL, but also when its 0.
    All objects with an ID in the DerStandard database have auto-increment disabled
    in our database.
    """
    async with empty_session() as s, s.begin():
        objects = [zero_object(tp) for tp in objtypes]
        s.add_all(objects)

    # Read back the object.
    async with empty_session() as s, s.begin():
        for obj in objects:
            result = await s.get(obj.__class__, 0)
            assert result is not None


@pytest.mark.parametrize("objtype", [Thread, TickerPosting, ArticlePosting])
async def test_add_id_zero_error(
    empty_session: async_sessionmaker[AsyncSession], objtype: str, zero_object
):
    """Add objects with ID set to 0 while violating foreign key constraints.

    All of our supported engines should detect this as an error.
    """
    with pytest.raises(Exception) as excinfo:
        async with empty_session() as s, s.begin():
            obj = zero_object(objtype)
            s.add(obj)
    assert "IntegrityError" in excinfo.value.__class__.__name__
    assert "foreign key constraint" in str(excinfo.value).lower()


async def test_load_parent_posting(empty_session: async_sessionmaker[AsyncSession]):
    """Load a posting and check if eager loading of the parent works."""
    ts = dt.datetime.now()
    user = User(0, deleted=ts)
    article = Article(0, None, ts, None, None, None, [])
    parent = ArticlePosting(0, None, user, None, ts, 0, 0, None, None, article)
    child = ArticlePosting(1, None, user, parent, ts, 0, 0, None, None, article)

    async with empty_session() as s, s.begin():
        s.add_all([user, article, parent, child])

    # Read back the child and check if we can access the parent.
    async with empty_session() as s, s.begin():
        result = await s.get(ArticlePosting, child.id)
        assert result is not None
        assert result.parent is not None
