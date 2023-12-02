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

"""Unified API for derstandard.at."""

__all__ = ("DerStandardAPI", "ReadOnlySessionError")


from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from .webapi import WebAPI


class ReadOnlySessionError(Exception):
    """Raise when a disallowed function is called."""

    pass


class DerStandardAPI:
    """Unified API for derstandard.at with a database cache."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._dbsession = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def db(self, readonly: bool = True) -> AsyncGenerator[AsyncSession, None]:
        """Access to the database session.

        The session is created and begin() is called. If read-only is set to true, then
        some functions of the session are not available and the session is rolled back
        at the end, making all changes non-persistent.
        Note that there is probably a way around it, but it should be safe enough for
        the most common scenarios.
        """
        async with self._dbsession() as s, s.begin():
            if readonly:
                s.add = self._not_allowed("add", async_=False)  # type: ignore
                s.add_all = self._not_allowed("add_all", async_=False)  # type: ignore
                s.commit = self._not_allowed("commit", async_=True)  # type: ignore
                s.delete = self._not_allowed("delete", async_=True)  # type: ignore
                s.expire = self._not_allowed("expire", async_=False)  # type: ignore
                s.flush = self._not_allowed("flush", async_=True)  # type: ignore
                s.merge = self._not_allowed("merge", async_=True)  # type: ignore

            yield s

            if readonly:
                await s.rollback()

    def web(self) -> WebAPI:
        """Access to the web API.

        Always request from the web API and store the result in the local database.
        """
        return WebAPI(self._dbsession)

    def _not_allowed(self, name: str, async_: bool = False) -> Any:
        """Create a function that raises and exception."""

        def func(*args: Any, **kwargs: Any) -> Any:
            msg = f"function '{name}' not allowed for read-only sessions"
            raise ReadOnlySessionError(msg)

        async def afunc(*args: Any, **kwargs: Any) -> Any:
            msg = f"function '{name}' not allowed for read-only sessions"
            raise ReadOnlySessionError(msg)

        if async_:
            return afunc
        else:
            return func
