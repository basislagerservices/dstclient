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
from typing import Optional, SupportsInt

from sqlalchemy import ForeignKey
from sqlalchemy.orm import mapped_column, registry, Mapped, relationship


# Type registry for dataclasses.
type_registry = registry()


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
    """ID of the user."""

    type: Mapped[str]
    """Type of the user (deleted, full)."""

    postings: Mapped[list[TickerPosting]] = relationship(back_populates="user")
    """Postings written by this user."""

    threads: Mapped[list[Thread]] = relationship(back_populates="user")
    """Threads written by this user."""

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

    def __init__(self, id: SupportsInt, name: str, registered: dt.datetime) -> None:
        """Create a new full user object."""
        super().__init__(id)
        self.name = name
        self.registered = registered
        self.deleted = None

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
    __tablename__ = "ticker"

    def __init__(self, id: SupportsInt, last_modified: dt.datetime) -> None:
        """Create a new ticker object."""
        self.id = int(id)
        self.last_modified = last_modified

    id: Mapped[int] = mapped_column(primary_key=True)
    """ID of this ticker."""

    last_modified: Mapped[dt.datetime]
    """Datetime this ticker was last modified."""

    threads: Mapped[list[Thread]] = relationship(back_populates="ticker")
    """Threads in this ticker."""


@type_registry.mapped
class Thread:
    __tablename__ = "thread"

    def __init__(
        self,
        id: SupportsInt,
        published: dt.datetime,
        ticker: Ticker,
        user: User,
        upvotes: SupportsInt,
        downvotes: SupportsInt,
        title: Optional[str],
        message: Optional[str],
    ) -> None:
        """Create a new thread object."""
        self.id = int(id)
        self.published = published
        self.ticker = ticker
        self.user = user
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
    __tablename__ = "article"

    def __init__(self, id: int, published: dt.datetime) -> None:
        """Create a new article."""
        self.id = id
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
        user: User,
        parent: None | Posting,
        published: dt.datetime,
        upvotes: SupportsInt,
        downvotes: SupportsInt,
        title: Optional[str],
        message: Optional[str],
    ) -> None:
        """Do not use this directly."""

        self.id = int(id)
        self.user = user
        self.parent = parent
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
        thread: Thread,
    ) -> None:
        super().__init__(
            id,
            user,
            parent,
            published,
            upvotes,
            downvotes,
            title,
            message,
        )
        self.thread = thread

    thread_id: Mapped[int] = mapped_column(ForeignKey("thread.id"), nullable=True)
    """ID of the thread this posting belongs to."""
    thread: Mapped[Thread] = relationship(lazy="immediate")
    """The thread where this posting was published."""

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
        parent: None | Posting,
        published: dt.datetime,
        upvotes: SupportsInt,
        downvotes: SupportsInt,
        title: Optional[str],
        message: Optional[str],
        article: Article,
    ) -> None:
        super().__init__(
            id, user, parent, published, upvotes, downvotes, title, message
        )
        self.article = article

    article_id: Mapped[int] = mapped_column(ForeignKey("article.id"), nullable=True)
    """ID of the article this posting belongs to."""
    article: Mapped[Article] = relationship(lazy="immediate")
    """The article where this posting was published."""

    __mapper_args__ = {
        "polymorphic_identity": "article",
    }
