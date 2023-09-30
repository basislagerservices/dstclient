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
)

import datetime as dt
from typing import Optional, Union

from sqlalchemy import ForeignKey, ForeignKeyConstraint
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
    __tablename__ = "user"

    def __init__(self, id: int, name: str) -> None:
        """Create a new user object."""
        self.id = id
        self.name = name

    id: Mapped[int] = mapped_column(primary_key=True)
    """ID of the user."""

    name: Mapped[str]
    """Name of the user."""

    # TODO: Add created date.

    postings: WriteOnlyMapped[list["TickerPosting"]] = relationship(
        back_populates="user"
    )
    """Postings written by this user."""

    threads: WriteOnlyMapped[list["Thread"]] = relationship(back_populates="user")
    """Threads written by this user."""


@type_registry.mapped
class Ticker:
    __tablename__ = "ticker"

    def __init__(self, id: int, published: dt.datetime) -> None:
        """Create a new ticker object."""
        self.id = id
        self.published = published

    id: Mapped[int] = mapped_column(primary_key=True)
    """ID of this ticker."""

    published: Mapped[dt.datetime]
    """Datetime this ticker was published."""

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
    ticker: Mapped[Ticker] = relationship()
    """The ticker this thread belongs to."""

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    """ID of the user who has published this thread."""
    user: Mapped[User] = relationship()
    """The user who posted this."""

    upvotes: Mapped[int]
    """Number of upvotes if fetched."""

    downvotes: Mapped[int]
    """Number of downvotes if fetched."""

    title: Mapped[Optional[str]] = None
    """Title of the thread posting."""

    message: Mapped[Optional[str]] = None
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
    user: Mapped[User] = relationship()
    """The user who posted this."""

    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("posting.id"))
    """Optional ID of a parent posting."""
    parent: Mapped[Optional["Posting"]] = relationship(remote_side=[id])
    """Optional parent posting."""

    published: Mapped[dt.datetime]
    """Datetime this posting was published."""

    upvotes: Mapped[int]
    """Number of upvotes if fetched."""

    downvotes: Mapped[int]
    """Number of downvotes if fetched."""

    title: Mapped[Optional[str]] = None
    """Title of the posting."""

    message: Mapped[Optional[str]] = None
    """Content of the posting."""

    __mapper_args__ = {
        "polymorphic_identity": "posting",
        "polymorphic_on": "type",
    }


@type_registry.mapped
class TickerPosting(Posting):
    """Posting in a ticker."""

    __tablename__ = "tickerposting"

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

    id: Mapped[int] = mapped_column(ForeignKey("posting.id"), primary_key=True)
    """ID of this posting."""

    thread_id: Mapped[int] = mapped_column(ForeignKey("thread.id"))
    """ID of the thread this posting belongs to."""
    thread: Mapped[Thread] = relationship()
    """The thread where this posting was published."""

    __mapper_args__ = {
        "polymorphic_identity": "ticker",
    }


@type_registry.mapped
class ArticlePosting(Posting):
    """Posting in an article forum."""

    __tablename__ = "articleposting"

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
        if isinstance(article, Thread):
            self.article = article
        elif isinstance(article, int):
            self.article_id = article
        else:
            raise TypeError("invalid type for article")

    id: Mapped[int] = mapped_column(ForeignKey("posting.id"), primary_key=True)
    """ID of this posting."""

    article_id: Mapped[int] = mapped_column(ForeignKey("article.id"))
    """ID of the article this posting belongs to."""
    article: Mapped[Article] = relationship()
    """The article where this posting was published."""

    __mapper_args__ = {
        "polymorphic_identity": "article",
    }
