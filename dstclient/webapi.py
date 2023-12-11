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


__all__ = ("WebAPI", "Ressort")


import asyncio
import concurrent
import datetime as dt
import enum
import itertools
import json
import os
import re
import time
from types import TracebackType
from typing import Any, AsyncIterator, Literal, Optional, SupportsInt, cast

from aiohttp import ClientError, ClientResponseError, ClientSession, TCPConnector

from async_lru import alru_cache

import backoff

from bs4 import BeautifulSoup

import dateutil.parser as dateparser

from gql import Client
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportError, TransportQueryError

import html2text

import pytz

from selenium.webdriver.common.by import By

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import tqdm

from . import gql_queries
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


class Ressort(enum.StrEnum):
    """Ressort available for queries."""

    FRONTPAGE = "frontpage"
    INTERNATIONAL = "international"
    INLAND = "inland"
    WIRTSCHAFT = "wirtschaft"
    WEB = "web"
    SPORT = "sport"
    PANORAMA = "panorama"
    KULTUR = "kultur"
    ETAT = "etat"
    WISSENSCHAFT = "wissenschaft"
    LIFESTYLE = "lifestyle"
    DISKURS = "diskurs"
    KARRIERE = "karriere"
    IMMOBILIEN = "immobilien"
    ZUKUNFT = "zukunft"
    GESUNDHEIT = "gesundheit"
    RECHT = "recht"
    DIESTANDARD = "diestandard"
    PODCAST = "podcast"
    VIDEO = "video"


class WebAPI:
    """Unified API for tickers and forums.

    There are basically two modes, one with a database sessionmaker and one without it.
    With a sessionmaker, downloaded data is inserted into the database.
    """

    RETRY_EXCEPTIONS = (ClientError, TransportError, TimeoutError)
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

        # Factory for database sessions and a lock for concurrent access.
        # TODO: Not all backends require locking.
        self._db_session = db_session
        self._db_lock = asyncio.Lock()

    def TURL(self, tail: str) -> str:
        """Construct an URL for a ticker API request."""
        return "https://www.derstandard.at/jetzt/api/" + tail

    def session(self, **kwargs: Any) -> ClientSession:
        """Create a client session with credentials."""
        headers = {"content-type": "application/json"}
        return ClientSession(
            cookies=self._cookies,
            headers=headers,
            connector=self._conn,
            connector_owner=False,
            raise_for_status=True,
            **kwargs,
        )

    async def __aenter__(self) -> "WebAPI":
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
            async with self._db_lock, self._db_session() as ds, ds.begin():
                for name in topics:
                    query = select(Topic).where(Topic.name == name)
                    if existing := (await ds.execute(query)).scalar():
                        entries.append(existing)
                    else:
                        topic = Topic(name)
                        ds.add(topic)
                        entries.append(topic)
        else:
            entries = [Topic(t) for t in topics]

        return entries

    ###########################################################################
    # User API                                                                #
    ###########################################################################
    @backoff.on_exception(backoff.expo, RETRY_EXCEPTIONS, max_value=RETRY_MAX_TIME)
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
            query, params = gql_queries.legacy_profile_public(legacy_id)
            try:
                response = await c.execute(query, variable_values=params)
                userdata = response["getCommunityMemberPublic"]
                user = User(
                    legacy_id,
                    object_id=userdata["memberId"],
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
                    deleted = dt.datetime.utcnow().replace(microsecond=0)
                    if self._db_session:
                        async with self._db_lock, self._db_session() as ds, ds.begin():
                            stmt = select(User.deleted).where(User.id == int(legacy_id))
                            if old_deleted := (await ds.execute(stmt)).scalar():
                                deleted = old_deleted

                    user = User(legacy_id, deleted=deleted)
                else:
                    raise

            if self._db_session:
                async with self._db_lock, self._db_session() as ds, ds.begin():
                    user = await ds.merge(user)

            return user

    @backoff.on_exception(backoff.expo, RETRY_EXCEPTIONS, max_value=RETRY_MAX_TIME)
    async def _get_user_relationships(self, user: User) -> Relationships:
        """Get a tuple of followees and followers of a user."""
        transport = AIOHTTPTransport(
            url="https://api-gateway.prod.cloud.ds.at/forum-serve-graphql/v1/"
        )
        async with Client(transport=transport, schema=self._schema) as c:
            assert isinstance(user.object_id, str)
            query, params = gql_queries.member_relationships_public(user.object_id)
            response = await c.execute(query, variable_values=params)
            followees = response["getMemberRelationshipsPublic"]["followees"]
            follower = response["getMemberRelationshipsPublic"]["follower"]

            def entry(data: Any) -> User:
                return User(
                    data["member"]["legacyId"],
                    object_id=data["member"]["memberId"],
                    name=data["member"]["name"],
                    registered=dt.datetime.fromisoformat(
                        data["member"]["memberCreatedAt"]
                    ),
                )

            followees = {entry(e) for e in followees}
            follower = {entry(e) for e in follower}

            return Relationships(followees, follower)

    ###########################################################################
    # Ticker API                                                              #
    ###########################################################################
    @backoff.on_exception(backoff.expo, RETRY_EXCEPTIONS, max_value=RETRY_MAX_TIME)
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

            ticker = Ticker(
                id=ticker_id,
                object_id=None,
                title=title,  # type: ignore
                published=published,
                topics=topics,
            )
            if self._db_session:
                async with self._db_lock, self._db_session() as ds, ds.begin():
                    ticker = await ds.merge(ticker)

            return ticker

    @backoff.on_exception(backoff.expo, RETRY_EXCEPTIONS, max_value=RETRY_MAX_TIME)
    async def get_ticker_threads(self, ticker: Ticker) -> AsyncIterator[Thread]:
        """Get a list of thread IDs of a ticker."""
        # TODO: Use paging instead of downloading all threads.
        url = self.TURL(f"redcontent?id={ticker.id}&ps={2**16}")
        async with self.session() as s, s.get(url) as resp:
            data = await resp.json()

        threads = [
            Thread(
                id=t["id"],
                object_id=None,
                published=dateparser.parse(t["ctd"]).astimezone(pytz.utc),
                ticker=ticker,
                title=t.get("hl"),
                message=t.get("cm"),
                user=await self.get_user(t["cid"]),
                upvotes=t["vp"],
                downvotes=t["vn"],
            )
            for t in data["rcs"]
        ]

        if self._db_session:
            async with self._db_lock, self._db_session() as ds, ds.begin():
                for i, t in enumerate(threads):
                    threads[i] = await ds.merge(t)

        for thread in threads:
            yield thread

    @backoff.on_exception(backoff.expo, RETRY_EXCEPTIONS, max_value=RETRY_MAX_TIME)
    async def _get_thread_postings_page(
        self,
        thread: Thread,
        *,
        skip_to: None | SupportsInt = None,
    ) -> list[TickerPosting]:
        """Get a single page of postings from a ticker thread.

        Returns a list of postings and the next page.
        """
        url = self.TURL(
            f"postings?objectId={thread.ticker.id}&redContentId={thread.id}"
        )
        if skip_to:
            url += f"&skipToPostingId={skip_to}"

        async with self.session() as s, s.get(url) as resp:
            page = await resp.json()

        postings = [
            TickerPosting(
                id=p["pid"],
                object_id=None,
                parent=p["ppid"],
                user=await self.get_user(p["cid"]),
                thread=thread,
                published=dateparser.parse(p["cd"]).astimezone(pytz.utc),
                title=p.get("hl"),
                message=p.get("tx"),
                upvotes=p["vp"],
                downvotes=p["vn"],
            )
            for p in page["p"]
        ]
        return postings

    @backoff.on_exception(backoff.expo, RETRY_EXCEPTIONS, max_value=RETRY_MAX_TIME)
    async def get_thread_postings(
        self,
        thread: Thread,
        *,
        progress_bar: tqdm.tqdm | None = None,  # type: ignore
    ) -> AsyncIterator[TickerPosting]:
        """Get all postings in a ticker thread."""

        postings = await self._get_thread_postings_page(thread)
        while postings:
            if self._db_session:
                async with self._db_lock, self._db_session() as ds, ds.begin():
                    for i, p in enumerate(postings):
                        postings[i] = await ds.merge(p)

            for p in postings:
                if progress_bar is not None:
                    progress_bar.update()
                yield p

            skip_to = postings[-1].id
            postings = await self._get_thread_postings_page(thread, skip_to=skip_to)

    ###########################################################################
    # Forum API                                                               #
    ###########################################################################
    @backoff.on_exception(backoff.expo, RETRY_EXCEPTIONS, max_value=RETRY_MAX_TIME)
    async def get_article(self, article_id: SupportsInt) -> Article:
        """Get an article."""
        url = f"https://www.derstandard.at/story/{article_id}"
        async with self.session() as s, s.get(url) as resp:
            page = await resp.text()

            # We get tags and the publishing date from the page config object.
            config = self._page_config(page)
            topics = await self._get_topics(config["nodes"])
            published = dt.datetime.fromisoformat(config["contentPublishingDate"])

            soup = BeautifulSoup(page, "lxml")
            content = None
            if div := soup.find("div", class_="article-body"):
                content = html2text.html2text(str(div))

            try:
                title = config["contentTitle"].strip()
            except KeyError:
                title = None

            try:
                summary = config["contentSummary"].strip()
            except KeyError:
                summary = None

            article = Article(
                article_id,
                object_id=None,
                published=published.replace(microsecond=0),
                title=title,
                summary=summary,
                content=content,
                topics=topics,
            )
            if self._db_session:
                async with self._db_lock, self._db_session() as ds, ds.begin():
                    article = await ds.merge(article)
            return article

    @backoff.on_exception(backoff.expo, RETRY_EXCEPTIONS, max_value=RETRY_MAX_TIME)
    async def _get_article_postings_page(
        self,
        article: Article,
        forum_id: str,
        cursor: str | None = None,
    ) -> tuple[list[ArticlePosting], str | None]:
        """Get a single page of postings from an article.

        Returns a tuple of a list of postings and a cursor for the next page.
        """
        transport = AIOHTTPTransport(
            url="https://api-gateway.prod.cloud.ds.at/forum-serve-graphql/v1/"
        )
        async with Client(transport=transport, schema=self._schema) as c:
            query, params = gql_queries.threads_by_forum_query(forum_id, cursor)
            response = await c.execute(query, variable_values=params)

        postings = []

        async def flatten(p: Any, parent: ArticlePosting | None = None) -> None:
            nonlocal postings
            legacy_id = p["author"]["legacyData"]["legacyCommunityIdentity"]
            if not legacy_id:
                user = None
            else:
                user = await self.get_user(legacy_id)

            published = dateparser.parse(p["history"]["created"])

            def get_rating(name: str) -> int:
                """Get a statistics dict from the posting."""
                try:
                    v = [e for e in p["reactions"]["aggregated"] if e["name"] == name]
                    return cast(int, v[0]["value"])
                except IndexError:
                    return 0

            ap = ArticlePosting(
                id=p["legacy"]["postingId"],
                object_id=p["id"],
                user=user,
                parent=parent,
                published=published,
                upvotes=get_rating("positive"),
                downvotes=get_rating("negative"),
                title=p.get("title"),
                message=p.get("text"),
                article=article,
            )
            postings.append(ap)
            for reply in p["replies"]:
                await flatten(reply, ap)

        for edge in response["getForumRootPostingsV2"]["edges"]:
            await flatten(edge["node"])

        next_page = None
        if response["getForumRootPostingsV2"]["pageInfo"]["hasNextPage"]:
            next_page = response["getForumRootPostingsV2"]["pageInfo"]["nextCursor"]

        return postings, next_page

    @backoff.on_exception(backoff.expo, RETRY_EXCEPTIONS, max_value=RETRY_MAX_TIME)
    async def get_article_postings(
        self,
        article: Article,
        *,
        progress_bar: tqdm.tqdm | None = None,  # type: ignore
    ) -> AsyncIterator[ArticlePosting]:
        """Get postings from an article."""
        transport = AIOHTTPTransport(
            url="https://api-gateway.prod.cloud.ds.at/forum-serve-graphql/v1/"
        )
        try:
            async with Client(transport=transport, schema=self._schema) as c:
                # Get the forum ID first.
                query, params = gql_queries.get_forum_info(article.id)
                response = await c.execute(query, variable_values=params)
                forum_id = response["getForumByContextUri"]["id"]
        except TransportQueryError as e:
            data = json.loads(e.args[0].replace("'", '"'))
            # Some articles don't have forums, for instance 212449.
            if data["message"] == "Forum not found.":
                return
            raise

        postings, cursor = await self._get_article_postings_page(article, forum_id)
        while postings:
            if self._db_session:
                async with self._db_lock, self._db_session() as ds, ds.begin():
                    for i, p in enumerate(postings):
                        postings[i] = await ds.merge(p)

            for p in postings:
                if progress_bar is not None:
                    progress_bar.update()
                yield p

            if cursor is None:
                break

            postings, cursor = await self._get_article_postings_page(
                article,
                forum_id=forum_id,
                cursor=cursor,
            )

    ###########################################################################
    # General website API                                                     #
    ###########################################################################
    @staticmethod
    def _timeline_url(date: dt.date, ressort: str) -> str:
        return f"https://www.derstandard.at/{ressort.lower()}/{date.year}/{date.month}/{date.day}"

    @backoff.on_exception(backoff.expo, RETRY_EXCEPTIONS, max_value=RETRY_MAX_TIME)
    async def _get_ressort_entries(
        self,
        ressort: str,
        date: dt.date,
    ) -> tuple[list[tuple[Literal["article", "ticker"], int]], dt.date | None]:
        """Get ressort entries for the given date.

        Returns a tuple (article_ids, ticker_ids, next_date).
        """
        try:
            url = self._timeline_url(date, ressort)
            async with self.session() as s, s.get(url) as resp:
                text = await resp.text()
                expr = r"(/story/(?P<article_id>[0-9]+))|(/jetzt/livebericht/(?P<ticker_id>[0-9]+))"
                entries: list[tuple[Literal["article", "ticker"], int]] = []
                for match in re.finditer(expr, text):
                    if match["ticker_id"]:
                        entries.append(("ticker", int(match["ticker_id"])))
                    if match["article_id"]:
                        entries.append(("article", int(match["article_id"])))

                # Get the next date without loading too many pages.
                soup = BeautifulSoup(text, "lxml")
                if (div := soup.find("div", class_="overview-readmore")) is not None:
                    a = div.find("a")
                    _, year, month, day = a.get("href").rsplit("/", maxsplit=3)  # type: ignore
                    next_date = dt.date(int(year), int(month), int(day))
                else:
                    next_date = None

                return (entries, next_date)

        except ClientResponseError as e:
            # We get 404 errors when the date doesn't have any entries, so we ignore it.
            if e.status == 404:
                return ([], date - dt.timedelta(days=1))
            raise

    async def get_ressort_entries(
        self,
        ressort: str,
        start_date: dt.date,
        end_date: dt.date | None = None,
        *,
        progress_bar: tqdm.tqdm | None = None,  # type: ignore
    ) -> AsyncIterator[tuple[Literal["ticker", "article"], int]]:
        """Get the IDs of articles and tickers in a ressort between two given dates.

        Dates are only a guideline and returned entries might be outside the given
        date range. Entries are returned from the end_date to the past.

        Returns an iterator with tuples ("ticker"|"article", id).
        """
        if end_date is None:
            end_date = dt.date.today()

        date: dt.date | None = end_date

        if progress_bar is not None:
            progress_bar.total = max((end_date - start_date).days + 1, 0)

        while date is not None and date >= start_date:
            entries, next_date = await self._get_ressort_entries(ressort, date)

            if progress_bar is not None:
                if next_date is None or next_date < start_date:  # Finished
                    progress_bar.n = progress_bar.total
                    progress_bar.refresh()
                else:
                    progress_bar.update((date - next_date).days)

            date = next_date

            for e in entries:
                yield e

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
