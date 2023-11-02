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
    "Posting",
    "Thread",
    "Ticker",
    "TickerPosting",
    "User",
    "DeletedUser",
    "FullUser",
)

import datetime as dt
from typing import Any, Optional, SupportsInt

from sqlalchemy import ForeignKey, Table, Column, Integer
from sqlalchemy.orm import Mapped, mapped_column, registry, relationship, validates


# Type registry for dataclasses.
type_registry = registry()


# Follower relationship for users.
# A user in the follower column follows a user in the followee column.
follower_relationship = Table(
    "follower_relationship",
    type_registry.metadata,
    Column("follower_user_id", Integer, ForeignKey("user.id"), primary_key=True),
    Column("followee_user_id", Integer, ForeignKey("user.id"), primary_key=True),
)


@type_registry.mapped
class User:
    """Base class for active and deleted users.

    This class is also used for partial users who have not been fully crawled.
    """

    __tablename__ = "user"

    def __init__(self, id: SupportsInt) -> None:
        """Create a new user object."""
        self.id = int(id)

    id: Mapped[int] = mapped_column(primary_key=True)
    """Legacy ID of the user."""

    type: Mapped[str]
    """Type of the user (deleted, full)."""

    postings: Mapped[list[TickerPosting]] = relationship(back_populates="user")
    """Postings written by this user."""

    threads: Mapped[list[Thread]] = relationship(back_populates="user")
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

    __mapper_args__ = {
        "polymorphic_identity": "user",
        "polymorphic_on": "type",
    }


@type_registry.mapped
class DeletedUser(User):
    """A user who was already deleted when first added to the database."""

    __mapper_args__ = {
        "polymorphic_identity": "deleted",
    }


@type_registry.mapped
class FullUser(User):
    """A user who was active when initially added to the database.

    The user might have been deleted later, but we still have all the
    basic information about them.
    """

    def __init__(
        self,
        id: SupportsInt,
        member_id: str,
        name: str,
        registered: dt.datetime,
    ) -> None:
        """Create a new full user object."""
        super().__init__(id)
        self.member_id = member_id
        self.name = name
        self.registered = registered
        self.deleted = None

    # TODO: Can we get this for deleted users?
    # TODO: Use as key, it will eventually supersede the legacy ID.
    member_id: Mapped[str] = mapped_column(nullable=True)
    """ID in the new backend."""

    name: Mapped[str] = mapped_column(nullable=True)
    """Name of the user."""

    registered: Mapped[dt.datetime] = mapped_column(nullable=True)
    """Time when the user was registered."""

    deleted: Mapped[Optional[dt.datetime]]
    """First time this user was encountered as deleted."""

    __mapper_args__ = {
        "polymorphic_identity": "full",
    }


@type_registry.mapped
class Ticker:
    """Database class for a ticker."""

    __tablename__ = "ticker"

    def __init__(
        self,
        id: SupportsInt,
        title: str | None,
        published: dt.datetime,
    ) -> None:
        """Create a new ticker object."""
        self.id = int(id)
        self.title = title
        self.published = published

    id: Mapped[int] = mapped_column(primary_key=True)
    """ID of this ticker."""

    title: Mapped[Optional[str]]
    """Title of the ticker."""

    published: Mapped[dt.datetime]
    """Datetime this ticker was published."""

    threads: Mapped[list[Thread]] = relationship(back_populates="ticker")
    """Threads in this ticker."""


@type_registry.mapped
class Thread:
    """Database class for a thread in a ticker."""

    __tablename__ = "thread"

    def __init__(
        self,
        id: SupportsInt,
        published: dt.datetime,
        ticker: SupportsInt | Ticker,
        user: SupportsInt | User,
        upvotes: SupportsInt,
        downvotes: SupportsInt,
        title: Optional[str],
        message: Optional[str],
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
        self.published = published
        self.upvotes = int(upvotes)
        self.downvotes = int(downvotes)
        self.title = title
        self.message = message

    id: Mapped[int] = mapped_column(primary_key=True)
    """ID of this thread."""

    published: Mapped[dt.datetime]
    """Datetime this thread was published."""

    ticker_id: Mapped[int] = mapped_column(ForeignKey("ticker.id"))
    """ID of the ticker this thread belongs to."""
    ticker: Mapped[Ticker] = relationship(lazy="immediate")
    """The ticker this thread belongs to."""

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    """ID of the user who has published this thread."""
    user: Mapped[User] = relationship(lazy="immediate")
    """The user who posted this."""

    upvotes: Mapped[int]
    """Number of upvotes if fetched."""

    downvotes: Mapped[int]
    """Number of downvotes if fetched."""

    title: Mapped[Optional[str]]
    """Title of the thread posting."""

    message: Mapped[Optional[str]]
    """Content of the thread posting."""

    postings: Mapped[list[TickerPosting]] = relationship(back_populates="thread")
    """Postings in this thread."""


@type_registry.mapped
class Article:
    """Database class for an article."""

    __tablename__ = "article"

    def __init__(self, id: SupportsInt, published: dt.datetime) -> None:
        """Create a new article."""
        self.id = int(id)
        self.published = published

    id: Mapped[int] = mapped_column(primary_key=True)
    """ID of this article."""

    published: Mapped[dt.datetime]
    """Datetime this article was published."""

    postings: Mapped[list[ArticlePosting]] = relationship(back_populates="article")
    """Postings in the article forum."""


@type_registry.mapped
class Posting:
    """Base class for postings."""

    __tablename__ = "posting"

    def __init__(
        self,
        id: SupportsInt,
        user: SupportsInt | User,
        parent: None | Posting | SupportsInt,
        published: dt.datetime,
        upvotes: SupportsInt,
        downvotes: SupportsInt,
        title: Optional[str],
        message: Optional[str],
    ) -> None:
        """Do not use this directly."""

        try:
            self.user_id = int(user)  # type: ignore
        except (TypeError, ValueError):
            if isinstance(user, User):
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
        self.published = published
        self.upvotes = int(upvotes)
        self.downvotes = int(downvotes)
        self.title = title
        self.message = message

    id: Mapped[int] = mapped_column(primary_key=True)
    """ID of this posting."""

    type: Mapped[str]
    """Type of the posting (ticker, article, ...)"""

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    """ID of the user who has published this posting."""
    user: Mapped[User] = relationship(lazy="immediate")
    """The user who posted this."""

    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("posting.id"))
    """Optional ID of a parent posting."""
    parent: Mapped[Optional[Posting]] = relationship(remote_side=[id], lazy="immediate")
    """Optional parent posting."""

    published: Mapped[dt.datetime]
    """Datetime this posting was published."""

    upvotes: Mapped[int]
    """Number of upvotes if fetched."""

    downvotes: Mapped[int]
    """Number of downvotes if fetched."""

    title: Mapped[Optional[str]]
    """Title of the posting."""

    message: Mapped[Optional[str]]
    """Content of the posting."""

    responses: Mapped[list[TickerPosting]] = relationship(back_populates="parent")
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
        user: User,
        parent: None | Posting,
        published: dt.datetime,
        upvotes: SupportsInt,
        downvotes: SupportsInt,
        title: Optional[str],
        message: Optional[str],
        thread: SupportsInt | Thread,
    ) -> None:
        super().__init__(
            id, user, parent, published, upvotes, downvotes, title, message
        )
        try:
            self.thread_id = int(thread)  # type: ignore
        except (TypeError, ValueError):
            if isinstance(thread, Thread):
                self.thread = thread
            else:
                raise TypeError("invalid type for thread")

    thread_id: Mapped[int] = mapped_column(ForeignKey("thread.id"), nullable=True)
    """ID of the thread this posting belongs to."""
    thread: Mapped[Thread] = relationship(lazy="immediate")
    """The thread where this posting was published."""

    @validates("thread", "thread_id")
    def validate_thread(self, key: str, value: Any) -> Any:
        """Validate that responses are in the same thread as the parent."""
        if self.parent is not None:
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
        user: User,
        parent: Optional[Posting],
        published: dt.datetime,
        upvotes: SupportsInt,
        downvotes: SupportsInt,
        title: Optional[str],
        message: Optional[str],
        article: SupportsInt | Article,
    ) -> None:
        super().__init__(
            id, user, parent, published, upvotes, downvotes, title, message
        )
        try:
            self.article_id = int(article)  # type: ignore
        except (TypeError, ValueError):
            if isinstance(article, Article):
                self.article = article
            else:
                raise TypeError("invalid type for article")

    article_id: Mapped[int] = mapped_column(ForeignKey("article.id"), nullable=True)
    """ID of the article this posting belongs to."""
    article: Mapped[Article] = relationship(lazy="immediate")
    """The article where this posting was published."""

    @validates("article", "article_id")
    def validate_article(self, key: str, value: Any) -> Any:
        """Validate that responses are in the same article as the parent."""
        if self.parent is not None:
            if key == "article" and value.id != self.parent.article.id:
                raise ValueError("parent posting is in a different article")
            elif key == "article_id" and value != self.parent.article.id:
                raise ValueError("parent posting is in a different article")

        return value

    __mapper_args__ = {
        "polymorphic_identity": "article",
    }
