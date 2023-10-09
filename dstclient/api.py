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

"""Unified API for tickers and forums."""


__all__ = ("DerStandardAPI",)


import asyncio
import concurrent
import contextlib
import datetime as dt
import itertools
import time
from typing import Any, AsyncContextManager, Optional, Union

from aiohttp import ClientSession

import dateutil.parser as dateparser

import pytz

from selenium.webdriver.common.by import By

from sqlalchemy import event, Engine
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    AsyncSession,
    create_async_engine,
    AsyncEngine,
)

from .types import Ticker, TickerPosting, Thread, FullUser, DeletedUser, type_registry
from .utils import chromedriver


def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
    """Set the foreign_keys pragma for SQLite databases."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


async def create_tables(engine: AsyncEngine) -> None:
    """Create tables in the database."""
    async with engine.begin() as conn:
        await conn.run_sync(type_registry.metadata.create_all)


class DerStandardAPI:
    """Unified API for tickers and forums."""

    def __init__(self, db_engine: Optional[AsyncEngine] = None) -> None:
        self._cookies: Optional[dict[str, str]] = None

        # Use an in-memory sqlite engine if none is specified.
        if db_engine is None:
            db_engine = create_async_engine(f"sqlite+aiosqlite://")

        # Ensure that the foreign_key pragma is set for sqlite.
        if db_engine.name == "sqlite":
            event.listen(Engine, "connect", set_sqlite_pragma)

        # Initialize tables.
        # TODO: Not sure if we should do this for every engine or only for the internal one.
        asyncio.run(create_tables(db_engine))

        self._db_engine = db_engine
        self._db_session = async_sessionmaker(self._db_engine, expire_on_commit=False)

    def TURL(self, tail: str) -> str:
        """Construct an URL for a ticker API request."""
        return "https://www.derstandard.at/jetzt/api/" + tail

    def FURL(self, tail: str) -> str:
        """Construct an URL for a forum API request."""
        return "https://capi.ds.at/forum-serve-graphql/v1/" + tail

    def session(self) -> ClientSession:
        """Create a client session with credentials."""
        headers = {"content-type": "application/json"}
        return ClientSession(cookies=self._cookies, headers=headers)

    def _session_context(
        self, client_session: Optional[ClientSession] = None
    ) -> AsyncContextManager[ClientSession]:
        if client_session:
            return contextlib.nullcontext(client_session)
        return self.session()

    def db_session(self) -> AsyncSession:
        """Get a database session for the engine associated with the API."""
        return self._db_session()

    ###########################################################################
    # Ticker API                                                              #
    ###########################################################################
    async def get_ticker(
        self,
        ticker_id: Union[int, str],
        *,
        client_session: Optional[ClientSession] = None,
    ) -> Ticker:
        """Get a ticker from the API."""
        url = self.TURL(f"redcontent?id={ticker_id}&ps=0")
        async with self._session_context(client_session) as session:
            async with session.get(url) as resp:
                ticker = await resp.json()
                return Ticker(int(ticker_id), dateparser.parse(ticker["lmd"]))

    async def get_ticker_threads(
        self,
        ticker_id: Union[int, str],
        *,
        client_session: Optional[ClientSession] = None,
    ) -> list[Thread]:
        """Get a list of thread IDs of a ticker."""
        url = self.TURL(f"redcontent?id={ticker_id}&ps=1000000")

        async with self._session_context(client_session) as session:
            async with session.get(url) as resp:
                return [
                    Thread(
                        id=t["id"],
                        published=dateparser.parse(t["ctd"]).astimezone(pytz.utc),
                        ticker=int(ticker_id),
                        title=t.get("hl") or None,
                        message=t.get("cm") or None,
                        user=FullUser(
                            id=t["cid"],
                            name=t["cn"],
                            registered=dt.datetime.now(),  # TODO: Use correct time
                        ),
                        upvotes=t["vp"],
                        downvotes=t["vn"],
                    )
                    for t in (await resp.json())["rcs"]
                ]

    async def _get_thread_postings_page(
        self,
        ticker_id: Union[int, str],
        thread_id: Union[int, str],
        skip_to: Union[None, int, str] = None,
        *,
        client_session: Optional[ClientSession] = None,
    ) -> Any:
        """Get a single page of postings from a ticker thread."""
        url = self.TURL(f"postings?objectId={ticker_id}&redContentId={thread_id}")
        if skip_to:
            url += f"&skipToPostingId={skip_to}"

        async with self._session_context(client_session) as session:
            async with session.get(url) as resp:
                return await resp.json()

    async def get_thread_postings(
        self,
        ticker_id: Union[int, str],
        thread_id: Union[int, str],
        *,
        client_session: Optional[ClientSession] = None,
    ) -> list[TickerPosting]:
        """Get all postings in a ticker thread."""
        postings = []
        page = await self._get_thread_postings_page(
            ticker_id,
            thread_id,
            client_session=client_session,
        )
        while page["p"]:
            postings.extend(page["p"])
            skip_to = page["p"][-1]["pid"]
            page = await self._get_thread_postings_page(
                ticker_id,
                thread_id,
                skip_to,
                client_session=client_session,
            )

        # Remove duplicates.
        postings = list({p["pid"]: p for p in postings}.values())
        return [
            TickerPosting(
                id=int(p["pid"]),
                parent=p["ppid"],
                user=FullUser(
                    id=int(p["cid"]),
                    name=p["cn"],
                    registered=dt.datetime.now(),  # TODO: Use correct time
                ),
                thread=int(thread_id),
                published=dateparser.parse(p["cd"]).astimezone(pytz.utc),
                title=p.get("hl") or None,
                message=p.get("tx") or None,
                upvotes=p["vp"],
                downvotes=p["vn"],
            )
            for p in postings
        ]

    ###########################################################################
    # Accept terms and conditions                                             #
    ###########################################################################
    async def update_cookies(self) -> None:
        """Update credentials and GDPR cookies."""
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            self._cookies = await loop.run_in_executor(pool, self._accept_conditions)

    def _accept_conditions(self, timeout: Optional[int] = None) -> dict[str, str]:
        """Accept terms and conditions and return necessary cookies.

        Cookies are in a format suitable for the aiohttp.ClientSession.
        """
        with chromedriver() as driver:
            driver.get("https://www.derstandard.at/consent/tcf/")
            it = itertools.count() if timeout is None else range(int(timeout + 0.5))
            for _ in it:
                # Find the correct iframe
                for element in driver.find_elements(By.TAG_NAME, "iframe"):
                    if element.get_attribute("title") == "SP Consent Message":
                        driver.switch_to.frame(element)
                        # Find the correct button and click it.
                        for button in driver.find_elements(By.TAG_NAME, "button"):
                            if button.get_attribute("title") == "Einverstanden":
                                button.click()
                                return {
                                    c["name"]: c["value"] for c in driver.get_cookies()
                                }
                    time.sleep(1)
            else:
                raise TimeoutError("accepting terms and conditions timed out")
