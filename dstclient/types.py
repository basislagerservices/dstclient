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
from typing import Optional, Union

from sqlalchemy import ForeignKey
from sqlalchemy.orm import (
    mapped_column,
    registry,
    Mapped,
    relationship,
    WriteOnlyMapped,
)


# Type registry for dataclasses.
type_registry = registry()


@type_registry.mapped
class User:
    """Base class for active and deleted users.

    This class is also used for partial users who have not been fully crawled.
    """

    __tablename__ = "user"

    def __init__(self, id: int) -> None:
        """Create a new user object."""
        self.id = id

    id: Mapped[int] = mapped_column(primary_key=True)
    """ID of the user."""

    type: Mapped[str]
    """Type of the user (deleted, full)."""

    postings: WriteOnlyMapped[list["TickerPosting"]] = relationship(
        back_populates="user"
    )
    """Postings written by this user."""

    threads: WriteOnlyMapped[list["Thread"]] = relationship(back_populates="user")
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

    def __init__(self, id: int, name: str, registered: dt.date) -> None:
        """Create a new full user object."""
        super().__init__(id)
        self.name = name
        self.registered = registered
        self.deleted = None

    name: Mapped[str] = mapped_column(nullable=True)
    """Name of the user."""

    registered: Mapped[dt.date] = mapped_column(nullable=True)
    """Date when the user was registered."""

    deleted: Mapped[Optional[dt.datetime]]
    """First time this user was encountered as deleted."""

    __mapper_args__ = {
        "polymorphic_identity": "full",
    }


@type_registry.mapped
class Ticker:
    __tablename__ = "ticker"

    def __init__(self, id: int, last_modified: dt.datetime) -> None:
        """Create a new ticker object."""
        self.id = id
        self.last_modified = last_modified

    id: Mapped[int] = mapped_column(primary_key=True)
    """ID of this ticker."""

    last_modified: Mapped[dt.datetime]
    """Datetime this ticker was last modified."""

    threads: WriteOnlyMapped[list["Thread"]] = relationship(back_populates="ticker")
    """Threads in this ticker."""


@type_registry.mapped
class Thread:
    __tablename__ = "thread"

    def __init__(
        self,
        id: int,
        published: dt.datetime,
        ticker: Union[int, Ticker],
        user: Union[int, User],
        upvotes: int,
        downvotes: int,
        title: Optional[str],
        message: Optional[str],
    ) -> None:
        """Create a new thread object.

        The ticker and the user who created it can be passed with the ID or the
        object itself. If only the ID is passed, then the entry must already exist in
        the database when the object is inserted.
        """

        if isinstance(ticker, Ticker):
            self.ticker = ticker
        elif isinstance(ticker, int):
            self.ticker_id = ticker
        else:
            raise TypeError("invalid type for ticker")

        if isinstance(user, User):
            self.user = user
        elif isinstance(user, int):
            self.user_id = user
        else:
            raise TypeError("invalid type for user")

        self.id = id
        self.published = published
        self.upvotes = upvotes
        self.downvotes = downvotes
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

    postings: WriteOnlyMapped[list["TickerPosting"]] = relationship(
        back_populates="thread"
    )
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

    postings: WriteOnlyMapped[list["ArticlePosting"]] = relationship(
        back_populates="article"
    )
    """Postings in the article forum."""


@type_registry.mapped
class Posting:
    """Base class for postings."""

    __tablename__ = "posting"

    def __init__(
        self,
        id: int,
        user: Union[int, User],
        parent: Union[None, int, "Posting"],
        published: dt.datetime,
        upvotes: int,
        downvotes: int,
        title: Optional[str],
        message: Optional[str],
    ) -> None:
        """Do not use this directly."""

        if isinstance(user, User):
            self.user = user
        elif isinstance(user, int):
            self.user_id = user
        else:
            raise TypeError("invalid type for user")

        if isinstance(parent, Posting):
            self.parent = parent
        elif isinstance(parent, int):
            self.parent_id = parent
        elif parent is None:
            pass
        else:
            raise TypeError("invalid type for parent")

        self.id = id
        self.published = published
        self.upvotes = upvotes
        self.downvotes = downvotes
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
    parent: Mapped[Optional["Posting"]] = relationship(
        remote_side=[id], lazy="immediate"
    )
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
        id: int,
        user: Union[int, User],
        parent: Union[None, int, "Posting"],
        published: dt.datetime,
        upvotes: int,
        downvotes: int,
        title: Optional[str],
        message: Optional[str],
        thread: Union[int, Thread],
    ) -> None:
        super().__init__(
            id, user, parent, published, upvotes, downvotes, title, message
        )
        if isinstance(thread, Thread):
            self.thread = thread
        elif isinstance(thread, int):
            self.thread_id = thread
        else:
            raise TypeError("invalid type for thread")

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
        id: int,
        user: Union[int, User],
        parent: Union[None, int, "Posting"],
        published: dt.datetime,
        upvotes: int,
        downvotes: int,
        title: Optional[str],
        message: Optional[str],
        article: Union[int, Article],
    ) -> None:
        super().__init__(
            id, user, parent, published, upvotes, downvotes, title, message
        )
        if isinstance(article, Article):
            self.article = article
        elif isinstance(article, int):
            self.article_id = article
        else:
            raise TypeError("invalid type for article")

    article_id: Mapped[int] = mapped_column(ForeignKey("article.id"), nullable=True)
    """ID of the article this posting belongs to."""
    article: Mapped[Article] = relationship(lazy="immediate")
    """The article where this posting was published."""

    __mapper_args__ = {
        "polymorphic_identity": "article",
    }
