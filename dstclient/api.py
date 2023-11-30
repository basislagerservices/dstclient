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

from contextlib import asynccontextmanager, AsyncExitStack
from typing import Any, AsyncGenerator

from .webapi import WebAPI

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, AsyncSession


class DerStandardAPI:
    """Unified API for derstandard.at with a database cache."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._dbsession = async_sessionmaker(engine, expire_on_commit=False)
        self._webapi = WebAPI()

    @asynccontextmanager
    async def db(self, readonly: bool = True) -> AsyncGenerator[AsyncSession, None]:
        """Access to the database session.

        The session is created and begin() is called.
        """
        # TODO: Make this session read-only be default.
        async with self._dbsession() as s, s.begin():
            yield s

    @property
    def web(self) -> Any:
        """Access to the web API.

        Always request from the web API and store the result in the local database.
        """
        return self._webapi
