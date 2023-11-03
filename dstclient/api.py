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
import datetime as dt
import itertools
import json
import os
import re
import time
from types import TracebackType
from typing import Any, Optional, SupportsInt

from aiohttp import ClientSession, TCPConnector

from async_lru import alru_cache

from bs4 import BeautifulSoup

import dateutil.parser as dateparser

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportQueryError

import pytz

from selenium.webdriver.common.by import By

from .types import (
    Article,
    ArticlePosting,
    DeletedUser,
    FullUser,
    Thread,
    Ticker,
    TickerPosting,
    User,
)
from .utils import chromedriver


class APIError(Exception):
    """Raised when the API returns an unexpected response."""

    pass


class DerStandardAPI:
    """Unified API for tickers and forums.

    All API functions ensure that the returned objects are complete in the sense
    that they can immediately be inserted into a database.
    """

    def __init__(self) -> None:
        self._cookies: Optional[dict[str, str]] = None

        # GraphQL transport and schema
        with open(os.path.join(os.path.dirname(__file__), "schema.graphql")) as fp:
            self._schema = fp.read()

        # Set the connector to None by default. If it is used outside a context manager, then
        # a new per-session pool is created. This is usually slower.
        self._conn: TCPConnector | None = None

    def TURL(self, tail: str) -> str:
        """Construct an URL for a ticker API request."""
        return "https://www.derstandard.at/jetzt/api/" + tail

    def session(self) -> ClientSession:
        """Create a client session with credentials."""
        headers = {"content-type": "application/json"}
        return ClientSession(
            cookies=self._cookies,
            headers=headers,
            connector=self._conn,
            connector_owner=False,
        )

    async def __aenter__(self) -> Any:
        """Initialize the API by downloading necessary cookies."""
        await self.update_cookies()

        # Create a connector when we enter the context and close it again when we
        # leave it. All sessions created in the context share this pool, making
        # parallel connections faster.
        self._conn = TCPConnector()

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the existing connection pool."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    ###########################################################################
    # Ticker API                                                              #
    ###########################################################################
    @alru_cache(maxsize=32536)
    async def get_user(
        self,
        legacy_id: SupportsInt,
        *,
        relationships: bool = False,
    ) -> User:
        """Get a user and their information."""
        transport = AIOHTTPTransport(
            url="https://api-gateway.prod.cloud.ds.at/forum-serve-graphql/v1/"
        )
        async with Client(transport=transport, schema=self._schema) as c:
            query = gql(
                """
                query LegacyProfilePublic ($legacyMemberId: ID) {
                    getCommunityMemberPublic (legacyMemberId: $legacyMemberId) {
                        name
                        memberId
                        memberCreatedAt
                    }
                }
                """
            )
            try:
                params = {"legacyMemberId": legacy_id}
                response = await c.execute(query, variable_values=params)
                userdata = response["getCommunityMemberPublic"]
                fulluser = FullUser(
                    legacy_id,
                    userdata["memberId"],
                    userdata["name"],
                    dt.datetime.fromisoformat(userdata["memberCreatedAt"]),
                )
                if relationships:
                    followees, followers = await self.get_user_relationships(fulluser)
                    fulluser.followees.update(followees)
                    fulluser.followers.update(followers)
                return fulluser

            except TransportQueryError as e:
                data = json.loads(e.args[0].replace("'", '"'))
                # It looks like we get "Userprofile not found" for non-existing
                # profiles and a # server error for deleted profiles.
                if data["message"].startswith("Userprofile not found") or data[
                    "message"
                ].startswith("One or more parameter values are not valid."):
                    return DeletedUser(legacy_id)

                raise

    async def get_user_relationships(
        self, user: FullUser
    ) -> tuple[set[FullUser], set[FullUser]]:
        """Get a tuple of followees and followers of a user."""
        transport = AIOHTTPTransport(
            url="https://api-gateway.prod.cloud.ds.at/forum-serve-graphql/v1/"
        )
        async with Client(transport=transport, schema=self._schema) as c:
            query = gql(
                """
                query MemberRelationshipsPublic ($memberId: ID!) {
                    getMemberRelationshipsPublic (memberId: $memberId) {
                        follower {
                            member {
                                legacyId
                                memberId
                                name
                                memberCreatedAt
                            }
                        }
                        followees {
                            member {
                                legacyId
                                memberId
                                name
                                memberCreatedAt
                            }
                        }
                    }
                }
                """
            )
            params = {"memberId": user.member_id}
            response = await c.execute(query, variable_values=params)
            followees = response["getMemberRelationshipsPublic"]["followees"]
            follower = response["getMemberRelationshipsPublic"]["follower"]

            def entry(data: Any) -> FullUser:
                return FullUser(
                    data["member"]["legacyId"],
                    data["member"]["memberId"],
                    data["member"]["name"],
                    dt.datetime.fromisoformat(data["member"]["memberCreatedAt"]),
                )

            followees = {entry(e) for e in followees}
            follower = {entry(e) for e in follower}

            return followees, follower

    async def get_ticker(self, ticker_id: SupportsInt) -> Ticker:
        """Get a ticker from the website API."""
        url = f"https://www.derstandard.at/jetzt/livebericht/{ticker_id}/"
        async with self.session() as s, s.get(url) as resp:
            # TODO: Fix typing issues with BeautifulSoup.
            # We get the title from the "regular" soup.
            soup = BeautifulSoup(await resp.text(), "lxml")
            title = soup.find("meta", {"name": "title"})["content"]  # type: ignore

            # The publishing date is in another soup inside a script tag.
            script = soup.find("script", {"id": "summary-slide"}).getText()  # type: ignore
            scriptsoup = BeautifulSoup(script, "lxml")
            published = dateparser.parse(
                scriptsoup.find("meta", {"itemprop": "datePublished"})["content"]  # type: ignore
            ).astimezone(pytz.utc)

            return Ticker(ticker_id, title, published)  # type: ignore

    async def get_ticker_threads(self, ticker: Ticker) -> list[Thread]:
        """Get a list of thread IDs of a ticker."""
        url = self.TURL(f"redcontent?id={ticker.id}&ps={2**16}")
        async with self.session() as s, s.get(url) as resp:
            return [
                Thread(
                    id=t["id"],
                    published=dateparser.parse(t["ctd"]).astimezone(pytz.utc),
                    ticker=ticker,
                    title=t.get("hl"),
                    message=t.get("cm"),
                    user=await self.get_user(t["cid"]),
                    upvotes=t["vp"],
                    downvotes=t["vn"],
                )
                for t in (await resp.json())["rcs"]
            ]

    async def _get_thread_postings_page(
        self,
        thread: Thread,
        *,
        skip_to: None | SupportsInt = None,
    ) -> Any:
        """Get a single page of postings from a ticker thread."""
        url = self.TURL(
            f"postings?objectId={thread.ticker.id}&redContentId={thread.id}"
        )
        if skip_to:
            url += f"&skipToPostingId={skip_to}"

        async with self.session() as s, s.get(url) as resp:
            return await resp.json()

    async def get_thread_postings(self, thread: Thread) -> list[TickerPosting]:
        """Get all postings in a ticker thread."""
        postings = []
        page = await self._get_thread_postings_page(thread)

        while page["p"]:
            postings.extend(page["p"])
            skip_to = page["p"][-1]["pid"]
            page = await self._get_thread_postings_page(thread, skip_to=skip_to)

        # Remove duplicates.
        postings = list({p["pid"]: p for p in postings}.values())
        return [
            TickerPosting(
                id=p["pid"],
                parent=p["ppid"],
                user=await self.get_user(p["cid"]),
                thread=thread,
                published=dateparser.parse(p["cd"]).astimezone(pytz.utc),
                title=p.get("hl"),
                message=p.get("tx"),
                upvotes=p["vp"],
                downvotes=p["vn"],
            )
            for p in postings
        ]

    async def get_article(self, article_id: int) -> Article:
        """Get an article."""
        url = f"https://www.derstandard.at/story/{article_id}"
        async with self.session() as s, s.get(url) as resp:
            page = await resp.text()
            m = re.search(r'"contentPublishingDate":"(?P<published>.+?)"', page)
            if m is None:
                raise APIError("publishing date not found")
            published = dt.datetime.fromisoformat(m["published"]).astimezone(pytz.utc)
            return Article(article_id, published)

    async def get_article_posting(self, article: Article) -> list[ArticlePosting]:
        """Get postings from an article."""
        raise NotImplementedError()

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
