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
    "Thread",
    "Ticker",
    "TickerPosting",
    "ArticlePosting",
    "User",
)

import datetime as dt
from typing import Optional

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
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    """ID of the user."""

    name: Mapped[str]
    """Name of the user."""

    postings: WriteOnlyMapped[list["TickerPosting"]] = relationship(
        back_populates="user"
    )
    """Postings written by this user."""

    threads: WriteOnlyMapped[list["Thread"]] = relationship(back_populates="user")
    """Threads written by this user."""


@type_registry.mapped
class Ticker:
    __tablename__ = "ticker"

    id: Mapped[int] = mapped_column(primary_key=True)
    """ID of this ticker."""

    published: Mapped[dt.datetime]
    """Datetime this ticker was published."""

    threads: WriteOnlyMapped[list["Thread"]] = relationship(back_populates="ticker")
    """Threads in this ticker."""


@type_registry.mapped
class Thread:
    __tablename__ = "thread"

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

    id: Mapped[int] = mapped_column(primary_key=True)
    """ID of this article."""

    published: Mapped[dt.datetime]
    """Datetime this article was published."""

    postings: WriteOnlyMapped[list["ArticlePosting"]] = relationship(
        back_populates="thread"
    )
    """Postings in the article forum."""


@type_registry.mapped
class Posting:
    """Base class for postings."""

    __tablename__ = "posting"

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

    id: Mapped[int] = mapped_column(ForeignKey("posting.id"), primary_key=True)
    """ID of this posting."""

    article_id: Mapped[int] = mapped_column(ForeignKey("article.id"))
    """ID of the article this posting belongs to."""
    article: Mapped[Thread] = relationship()
    """The article where this posting was published."""

    __mapper_args__ = {
        "polymorphic_identity": "article",
    }
