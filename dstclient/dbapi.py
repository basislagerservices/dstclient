#
# Copyright 2023 Basislager Services
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

"""API implementation for the database."""

from typing import SupportsInt

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncEngine

from .types import *


class EntryNotFoundError(Exception):
    """Raised when an entry is not found."""

    pass


class DatabaseAPI:
    """Basic repository API extended by custom database functions."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._dbsession = async_sessionmaker(engine, expire_on_commit=False)

    async def get_user(
        self,
        legacy_id: SupportsInt,
        *,
        relationships: bool = False,
    ) -> User:
        """Get the user with the given ID."""
        async with self._dbsession() as s, s.begin():
            if (user := s.get(User, int(legacy_id))) is not None:
                return user
            raise EntryNotFoundError("user with id {legacy_id} not found")

    async def get_user_relationships(self, user: User) -> Relationships:
        ...

    async def get_ticker(self, ticker_id: SupportsInt) -> Ticker:
        """Get the ticker with the given ID."""
        async with self._dbsession() as s, s.begin():
            if (ticker := s.get(Ticker, int(ticker_id))) is not None:
                return ticker
            raise EntryNotFoundError("ticker with id {ticker_id} not found")

    async def get_ticker_threads(self, ticker: Ticker) -> list[Thread]:
        ...

    async def get_thread_postings(self, thread: Thread) -> list[TickerPosting]:
        ...

    async def get_article(self, article_id: SupportsInt) -> Article:
        ...

    async def get_article_postings(self, article: Article) -> list[ArticlePosting]:
        ...
