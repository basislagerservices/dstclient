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

"""Types for crawler results."""

from __future__ import annotations

__all__ = (
    "Article",
    "ArticlePosting",
    "Metadata",
    "Posting",
    "Thread",
    "Ticker",
    "TickerPosting",
    "Topic",
    "User",
    "Relationships",
    "type_registry",
)

import datetime as dt
from collections import namedtuple
from typing import Any, SupportsInt, overload

from sqlalchemy import BigInteger, Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, registry, relationship, validates


Relationships = namedtuple("Relationships", ["followees", "followers"])
"""Relationships between users."""

# Type registry for dataclasses.
type_registry = registry()


# Follower relationship for users.
# A user in the follower column follows a user in the followee column.
follower_relationship = Table(
    "follower_relationship",
    type_registry.metadata,
    Column(
        "follower_user_id",
        BigInteger,
        ForeignKey("user.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "followee_user_id",
        BigInteger,
        ForeignKey("user.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


@type_registry.mapped
class User:
    """A user in the database.

    Most fields are optional because we can't get them for deleted users.
    """

    __tablename__ = "user"

    @overload
    def __init__(self, id: SupportsInt, *, deleted: dt.datetime) -> None:
        ...

    @overload
    def __init__(
        self,
        id: SupportsInt,
        *,
        object_id: str,
        name: str,
        registered: dt.datetime,
    ) -> None:
        ...

    def __init__(
        self,
        id: SupportsInt,
        *,
        object_id: str | None = None,
        name: str | None = None,
        registered: dt.datetime | None = None,
        deleted: dt.datetime | None = None,
    ) -> None:
        """Create a new full user object."""
        self.id = int(id)
        self.object_id = object_id
        self.name = name
        self.registered = registered
        self.deleted = deleted

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    """Legacy ID of the user."""

    object_id: Mapped[str | None] = mapped_column(String(64), index=True, unique=True)
    """ID in the new backend."""

    name: Mapped[str | None] = mapped_column(String(64))
    """Name of the user."""

    registered: Mapped[dt.datetime | None]
    """Time when the user was registered."""

    deleted: Mapped[dt.datetime | None]
    """First time this user was encountered as deleted."""

    postings: Mapped[list[TickerPosting]] = relationship(
        back_populates="user", cascade="all,delete"
    )
    """Postings written by this user."""

    threads: Mapped[list[Thread]] = relationship(
        back_populates="user", cascade="all,delete"
    )
    """Threads written by this user."""

    followees: Mapped[set["User"]] = relationship(
        secondary=follower_relationship,
        primaryjoin=id == follower_relationship.c.follower_user_id,
        secondaryjoin=id == follower_relationship.c.followee_user_id,
        back_populates="followers",
    )
    """List of users who are followed by this user."""

    followers: Mapped[set["User"]] = relationship(
        secondary=follower_relationship,
        primaryjoin=id == follower_relationship.c.followee_user_id,
        secondaryjoin=id == follower_relationship.c.follower_user_id,
        back_populates="followees",
    )
    """List of users who are following this user."""


# Map a ticker to topics.
ticker_topic = Table(
    "ticker_topic",
    type_registry.metadata,
    Column("ticker_id", BigInteger, ForeignKey("ticker.id", ondelete="CASCADE")),
    Column("topic_id", Integer, ForeignKey("topic.id", ondelete="CASCADE")),
)

# Map an article to topics.
article_topic = Table(
    "article_topic",
    type_registry.metadata,
    Column("article_id", BigInteger, ForeignKey("article.id")),
    Column("topic_id", Integer, ForeignKey("topic.id")),
)


@type_registry.mapped
class Topic:
    """Topic assigned to an Article or Ticker."""

    __tablename__ = "topic"

    def __init__(self, name: str) -> None:
        self.name = name

    id: Mapped[int] = mapped_column(primary_key=True)
    """ID of this topic."""

    name: Mapped[str] = mapped_column(String(128), unique=True)
    """Name of this topic."""

    articles: Mapped[set["Article"]] = relationship(
        secondary=article_topic, back_populates="topics"
    )
    """List of articles with this topic."""

    tickers: Mapped[set["Ticker"]] = relationship(
        secondary=ticker_topic, back_populates="topics"
    )
    """List of tickers with this topic."""


@type_registry.mapped
class Ticker:
    """Database class for a ticker."""

    __tablename__ = "ticker"

    def __init__(
        self,
        id: SupportsInt,
        object_id: str | None,
        title: str | None,
        published: dt.datetime,
        topics: list[Topic] | None = None,
    ) -> None:
        """Create a new ticker object."""
        self.id = int(id)
        self.object_id = object_id
        self.title = title
        self.published = published
        if topics is None:
            topics = []
        self.topics = topics

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    """ID of this ticker."""

    object_id: Mapped[str | None] = mapped_column(String(64), index=True, unique=True)
    """ID in the new backend."""

    title: Mapped[str | None] = mapped_column(String(512))
    """Title of the ticker."""

    published: Mapped[dt.datetime]
    """Datetime this ticker was published."""

    threads: Mapped[list[Thread]] = relationship(
        back_populates="ticker", cascade="all,delete"
    )
    """Threads in this ticker."""

    topics: Mapped[list["Topic"]] = relationship(
        secondary=ticker_topic,
        back_populates="tickers",
        cascade="all,delete",
        lazy="immediate",
    )
    """Topics of this ticker."""


@type_registry.mapped
class Thread:
    """Database class for a thread in a ticker."""

    __tablename__ = "thread"

    def __init__(
        self,
        id: SupportsInt,
        object_id: str | None,
        published: dt.datetime,
        ticker: SupportsInt | Ticker,
        user: SupportsInt | User,
        upvotes: SupportsInt,
        downvotes: SupportsInt,
        title: str | None,
        message: str | None,
    ) -> None:
        """Create a new thread object."""

        try:
            self.ticker_id = int(ticker)  # type: ignore
        except (TypeError, ValueError):
            if isinstance(ticker, Ticker):
                self.ticker = ticker
            else:
                raise TypeError("invalid type for ticker")

        try:
            self.user_id = int(user)  # type: ignore
        except (TypeError, ValueError):
            if isinstance(user, User):
                self.user = user
            else:
                raise TypeError("invalid type for user")

        self.id = int(id)
        self.object_id = object_id
        self.published = published
        self.upvotes = int(upvotes)
        self.downvotes = int(downvotes)
        self.title = title
        self.message = message

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    """ID of this thread."""

    object_id: Mapped[str | None] = mapped_column(String(64), index=True, unique=True)
    """ID in the new backend."""

    published: Mapped[dt.datetime]
    """Datetime this thread was published."""

    ticker_id: Mapped[int] = mapped_column(ForeignKey("ticker.id", ondelete="CASCADE"))
    """ID of the ticker this thread belongs to."""
    ticker: Mapped[Ticker] = relationship(lazy="immediate")
    """The ticker this thread belongs to."""

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    """ID of the user who has published this thread."""
    user: Mapped[User] = relationship(lazy="immediate")
    """The user who posted this."""

    upvotes: Mapped[int]
    """Number of upvotes if fetched."""

    downvotes: Mapped[int]
    """Number of downvotes if fetched."""

    title: Mapped[str | None] = mapped_column(String(256))
    """Title of the thread posting."""

    message: Mapped[str | None] = mapped_column(String(2048))
    """Content of the thread posting."""

    postings: Mapped[list[TickerPosting]] = relationship(
        back_populates="thread", cascade="all,delete"
    )
    """Postings in this thread."""


@type_registry.mapped
class Article:
    """Database class for an article."""

    __tablename__ = "article"

    # TODO: Record authors
    # TODO: Does an article have a new object ID?

    def __init__(
        self,
        id: SupportsInt,
        object_id: str | None,
        published: dt.datetime,
        title: str | None,
        summary: str | None,
        content: str | None,
        topics: list[Topic] | None = None,
    ) -> None:
        """Create a new article."""
        self.id = int(id)
        self.object_id = object_id
        self.published = published
        self.title = title
        self.summary = summary
        self.content = content
        if topics is None:
            topics = []
        self.topics = topics

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    """ID of this article."""

    object_id: Mapped[str | None] = mapped_column(String(64), index=True, unique=True)
    """ID in the new backend."""

    published: Mapped[dt.datetime]
    """Datetime this article was published."""

    title: Mapped[str | None] = mapped_column(String(512))
    """Title of the article."""

    summary: Mapped[str | None] = mapped_column(Text)
    """Summary of the article"""

    content: Mapped[str | None] = mapped_column(Text)
    """Content of the article."""

    postings: Mapped[list[ArticlePosting]] = relationship(
        back_populates="article", cascade="all,delete"
    )
    """Postings in the article forum."""

    topics: Mapped[list["Topic"]] = relationship(
        secondary=article_topic,
        back_populates="articles",
        cascade="all,delete",
        lazy="immediate",
    )
    """Topics of this article."""


@type_registry.mapped
class Posting:
    """Base class for postings."""

    __tablename__ = "posting"

    def __init__(
        self,
        id: SupportsInt,
        object_id: str | None,
        user: SupportsInt | User | None,
        parent: None | Posting | SupportsInt,
        published: dt.datetime,
        upvotes: SupportsInt,
        downvotes: SupportsInt,
        title: str | None,
        message: str | None,
    ) -> None:
        """Do not use this directly."""

        try:
            self.user_id = int(user)  # type: ignore
        except (TypeError, ValueError):
            if user is None:
                self.user = None
            elif isinstance(user, User):
                self.user = user
            else:
                raise TypeError("invalid type for user")

        try:
            self.parent_id = int(parent)  # type: ignore
        except (TypeError, ValueError):
            if parent is None or isinstance(parent, Posting):
                self.parent = parent
            else:
                raise TypeError("invalid type for parent")

        self.id = int(id)
        self.object_id = object_id
        self.published = published
        self.upvotes = int(upvotes)
        self.downvotes = int(downvotes)
        self.title = title
        self.message = message

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    """ID of this posting."""

    object_id: Mapped[str | None] = mapped_column(String(64), index=True, unique=True)
    """ID in the new backend."""

    type: Mapped[str] = mapped_column(String(64))
    """Type of the posting (ticker, article, ...)"""

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=True,
    )
    """ID of the user who has published this posting."""
    user: Mapped[User | None] = relationship(lazy="immediate")
    """The user who posted this."""

    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("posting.id", ondelete="CASCADE")
    )
    """Optional ID of a parent posting."""
    parent: Mapped[Posting | None] = relationship(
        remote_side=[id],
        lazy="joined",
        join_depth=32,  # This should be enough for all postings currently supported.
    )
    """Optional parent posting."""

    published: Mapped[dt.datetime]
    """Datetime this posting was published."""

    upvotes: Mapped[int]
    """Number of upvotes if fetched."""

    downvotes: Mapped[int]
    """Number of downvotes if fetched."""

    title: Mapped[str | None] = mapped_column(String(256))
    """Title of the posting."""

    message: Mapped[str | None] = mapped_column(String(1024))
    """Content of the posting."""

    responses: Mapped[list[TickerPosting]] = relationship(
        back_populates="parent", cascade="all,delete"
    )
    """Responses to this posting."""

    __mapper_args__ = {
        "polymorphic_identity": "posting",
        "polymorphic_on": "type",
    }


@type_registry.mapped
class TickerPosting(Posting):
    """Posting in a ticker."""

    def __init__(
        self,
        id: SupportsInt,
        object_id: str | None,
        user: User,
        parent: None | Posting,
        published: dt.datetime,
        upvotes: SupportsInt,
        downvotes: SupportsInt,
        title: str | None,
        message: str | None,
        thread: SupportsInt | Thread,
    ) -> None:
        super().__init__(
            id=id,
            object_id=object_id,
            user=user,
            parent=parent,
            published=published,
            upvotes=upvotes,
            downvotes=downvotes,
            title=title,
            message=message,
        )
        try:
            self.thread_id = int(thread)  # type: ignore
        except (TypeError, ValueError):
            if isinstance(thread, Thread):
                self.thread = thread
            else:
                raise TypeError("invalid type for thread")

    thread_id: Mapped[int] = mapped_column(
        ForeignKey("thread.id", ondelete="CASCADE"), nullable=True
    )
    """ID of the thread this posting belongs to."""
    thread: Mapped[Thread] = relationship(lazy="immediate")
    """The thread where this posting was published."""

    @validates("thread", "thread_id")
    def validate_thread(self, key: str, value: Any) -> Any:
        """Validate that responses are in the same thread as the parent."""
        if self.parent is not None:
            assert isinstance(self.parent, TickerPosting)
            if key == "thread" and value.id != self.parent.thread.id:
                raise ValueError("parent posting is in a different thread")
            elif key == "thread_id" and value != self.parent.thread.id:
                raise ValueError("parent posting is in a different thread")

        return value

    __mapper_args__ = {
        "polymorphic_identity": "ticker",
    }


@type_registry.mapped
class ArticlePosting(Posting):
    """Posting in an article forum."""

    def __init__(
        self,
        id: SupportsInt,
        object_id: str | None,
        user: User | None,
        parent: Posting | None,
        published: dt.datetime,
        upvotes: SupportsInt,
        downvotes: SupportsInt,
        title: str | None,
        message: str | None,
        article: SupportsInt | Article,
    ) -> None:
        super().__init__(
            id=id,
            object_id=object_id,
            user=user,
            parent=parent,
            published=published,
            upvotes=upvotes,
            downvotes=downvotes,
            title=title,
            message=message,
        )
        try:
            self.article_id = int(article)  # type: ignore
        except (TypeError, ValueError):
            if isinstance(article, Article):
                self.article = article
            else:
                raise TypeError("invalid type for article")

    article_id: Mapped[int] = mapped_column(
        ForeignKey("article.id", ondelete="CASCADE"), nullable=True
    )
    """ID of the article this posting belongs to."""
    article: Mapped[Article] = relationship(lazy="immediate")
    """The article where this posting was published."""

    @validates("article", "article_id")
    def validate_article(self, key: str, value: Any) -> Any:
        """Validate that responses are in the same article as the parent."""
        if self.parent is not None:
            assert isinstance(self.parent, ArticlePosting)
            if key == "article" and value.id != self.parent.article.id:
                raise ValueError("parent posting is in a different article")
            elif key == "article_id" and value != self.parent.article.id:
                raise ValueError("parent posting is in a different article")

        return value

    __mapper_args__ = {
        "polymorphic_identity": "article",
    }


@type_registry.mapped
class Metadata:
    """Dictionary for general-purpose metadata."""

    __tablename__ = "metadata"

    def __init__(self, key: str, value: str) -> None:
        self.key = key
        self.value = value

    key: Mapped[str] = mapped_column(String(256), primary_key=True)
    """Key of the metadata entry."""

    value: Mapped[str] = mapped_column(String(4096))
    """Value of the metadata entry."""
