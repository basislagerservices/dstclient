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

"""Unified API for tickers and forums."""


__all__ = ("WebAPI",)


import asyncio
import concurrent
import datetime as dt
import itertools
import json
import os
import re
import time
from types import TracebackType
from typing import Any, Optional, SupportsInt, cast

from aiohttp import ClientError, ClientSession, TCPConnector

from async_lru import alru_cache

import backoff

from bs4 import BeautifulSoup

import dateutil.parser as dateparser

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportError, TransportQueryError

import pytz

from selenium.webdriver.common.by import By

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .types import (
    Article,
    ArticlePosting,
    Relationships,
    Thread,
    Ticker,
    TickerPosting,
    Topic,
    User,
)
from .utils import chromedriver


class WebAPI:
    """Unified API for tickers and forums.

    There are basically two modes, one with a database sessionmaker and one without it.
    With a sessionmaker, downloaded data is inserted into the database.
    """

    RETRY_EXCEPTIONS = (ClientError, TransportError)
    """Exceptions that trigger a retry of a request."""

    RETRY_MAX_TIME = 300
    """Maximum backoff time in seconds."""

    def __init__(
        self, db_session: async_sessionmaker[AsyncSession] | None = None
    ) -> None:
        self._cookies: Optional[dict[str, str]] = None

        # GraphQL transport and schema
        with open(os.path.join(os.path.dirname(__file__), "schema.graphql")) as fp:
            self._schema = fp.read()

        # Set the connector to None by default. If it is used outside a context manager, then
        # a new per-session pool is created. This is usually slower.
        self._conn: TCPConnector | None = None

        # Factory for database sessions.
        self._db_session = db_session

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

    @staticmethod
    def _page_config(page: str) -> dict[str, Any]:
        """Extract the page config from a ticker or article page."""
        try:
            match = re.search(
                r"window\.DERSTANDARD\.pageConfig\.init\((?P<config>\{.*\})\);",
                page,
            )
            if match:
                return cast(dict[str, Any], json.loads(match["config"]))
            return dict()
        except (KeyError, TypeError):
            return dict()

    async def _get_topics(self, topics: list[str]) -> list[Topic]:
        """Create topic objects from a list of strings."""
        entries = []
        if self._db_session:
            async with self._db_session() as s, s.begin():
                for name in topics:
                    query = select(Topic).where(Topic.name == name)
                    if existing := (await s.execute(query)).scalar():
                        entries.append(existing)
                    else:
                        topic = Topic(name)
                        s.add(topic)
                        entries.append(topic)
        else:
            entries = [Topic(t) for t in topics]

        return entries

    ###########################################################################
    # Ticker API                                                              #
    ###########################################################################
    @backoff.on_exception(backoff.expo, RETRY_EXCEPTIONS, max_time=RETRY_MAX_TIME)
    @alru_cache(maxsize=65536)
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
                user = User(
                    legacy_id,
                    member_id=userdata["memberId"],
                    name=userdata["name"],
                    registered=dt.datetime.fromisoformat(userdata["memberCreatedAt"]),
                )
                if relationships:
                    r = await self._get_user_relationships(user)
                    user.followees.update(r.followees)
                    user.followers.update(r.followers)

            except TransportQueryError as e:
                data = json.loads(e.args[0].replace("'", '"'))
                # It looks like we get "Userprofile not found" for non-existing
                # profiles and a # server error for deleted profiles.
                msg = data["message"]
                if msg.startswith("Userprofile not found") or msg.startswith(
                    "One or more parameter values are not valid."
                ):
                    # Check if the user was already deleted.
                    deleted = dt.datetime.utcnow()
                    if self._db_session:
                        async with self._db_session() as ds, ds.begin():
                            stmt = select(User.deleted).where(User.id == int(legacy_id))
                            if old_deleted := (await ds.execute(stmt)).scalar():
                                deleted = old_deleted

                    user = User(legacy_id, deleted=deleted)
                else:
                    raise

            if self._db_session:
                async with self._db_session() as ds, ds.begin():
                    user = await ds.merge(user)

            return user

    @backoff.on_exception(backoff.expo, RETRY_EXCEPTIONS, max_time=RETRY_MAX_TIME)
    async def _get_user_relationships(self, user: User) -> Relationships:
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

            def entry(data: Any) -> User:
                return User(
                    data["member"]["legacyId"],
                    member_id=data["member"]["memberId"],
                    name=data["member"]["name"],
                    registered=dt.datetime.fromisoformat(
                        data["member"]["memberCreatedAt"]
                    ),
                )

            followees = {entry(e) for e in followees}
            follower = {entry(e) for e in follower}

            return Relationships(followees, follower)

    @backoff.on_exception(backoff.expo, RETRY_EXCEPTIONS, max_time=RETRY_MAX_TIME)
    async def get_ticker(self, ticker_id: SupportsInt) -> Ticker:
        """Get a ticker from the website API."""
        url = f"https://www.derstandard.at/jetzt/livebericht/{ticker_id}/"
        async with self.session() as s, s.get(url) as resp:
            page = await resp.text()
            # We get tags from the page config object.
            # TODO: Could we use the contentPublishingDate here as well instead of
            #       looking it up in the soup? They don't seem to match all the time.
            config = self._page_config(page)
            topics = await self._get_topics(config["nodes"])

            # TODO: Fix typing issues with BeautifulSoup.
            # We get the title from the "regular" soup.
            soup = BeautifulSoup(page, "lxml")
            title = soup.find("meta", {"name": "title"})["content"]  # type: ignore

            # The publishing date is in another soup inside a script tag.
            script = soup.find("script", {"id": "summary-slide"}).getText()  # type: ignore
            scriptsoup = BeautifulSoup(script, "lxml")
            published = dateparser.parse(
                scriptsoup.find("meta", {"itemprop": "datePublished"})["content"]  # type: ignore
            ).astimezone(pytz.utc)

            ticker = Ticker(ticker_id, title, published, topics=topics)  # type: ignore
            if self._db_session:
                async with self._db_session() as ds, ds.begin():
                    ticker = await ds.merge(ticker)

            return ticker

    @backoff.on_exception(backoff.expo, RETRY_EXCEPTIONS, max_time=RETRY_MAX_TIME)
    async def get_ticker_threads(self, ticker: Ticker) -> list[Thread]:
        """Get a list of thread IDs of a ticker."""
        url = self.TURL(f"redcontent?id={ticker.id}&ps={2**16}")
        async with self.session() as s, s.get(url) as resp:
            threads = []
            for t in (await resp.json())["rcs"]:
                thread = Thread(
                    id=t["id"],
                    published=dateparser.parse(t["ctd"]).astimezone(pytz.utc),
                    ticker=ticker,
                    title=t.get("hl"),
                    message=t.get("cm"),
                    user=await self.get_user(t["cid"]),
                    upvotes=t["vp"],
                    downvotes=t["vn"],
                )
                if self._db_session:
                    async with self._db_session() as ds, ds.begin():
                        thread = await ds.merge(thread)
                threads.append(thread)

            return threads

    @backoff.on_exception(backoff.expo, RETRY_EXCEPTIONS, max_time=RETRY_MAX_TIME)
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

    @backoff.on_exception(backoff.expo, RETRY_EXCEPTIONS, max_time=RETRY_MAX_TIME)
    async def get_thread_postings(self, thread: Thread) -> list[TickerPosting]:
        """Get all postings in a ticker thread."""
        raw_postings = []
        page = await self._get_thread_postings_page(thread)

        while page["p"]:
            raw_postings.extend(page["p"])
            skip_to = page["p"][-1]["pid"]
            page = await self._get_thread_postings_page(thread, skip_to=skip_to)

        # Remove duplicates.
        raw_postings = list({p["pid"]: p for p in raw_postings}.values())
        postings = []
        for p in raw_postings:
            posting = TickerPosting(
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
            if self._db_session:
                async with self._db_session() as ds, ds.begin():
                    posting = await ds.merge(posting)
            postings.append(posting)

        return postings

    ###########################################################################
    # Forum API                                                               #
    ###########################################################################
    @backoff.on_exception(backoff.expo, RETRY_EXCEPTIONS, max_time=RETRY_MAX_TIME)
    async def get_article(self, article_id: SupportsInt) -> Article:
        """Get an article."""
        url = f"https://www.derstandard.at/story/{article_id}"
        async with self.session() as s, s.get(url) as resp:
            page = await resp.text()

            # We get tags and the publishing date from the page config object.
            config = self._page_config(page)
            topics = await self._get_topics(config["nodes"])
            published = dt.datetime.fromisoformat(config["contentPublishingDate"])

            article = Article(article_id, published, topics=topics)
            if self._db_session:
                async with self._db_session() as ds, ds.begin():
                    article = await ds.merge(article)
            return article

    @backoff.on_exception(backoff.expo, RETRY_EXCEPTIONS, max_time=RETRY_MAX_TIME)
    async def get_article_postings(self, article: Article) -> list[ArticlePosting]:
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
