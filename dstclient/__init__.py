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

"""API implementation for derstandard.at."""


__all__ = (
    "DerStandardAPI",
    "ReadOnlySessionError",
    "WebAPI",
    "Ressort",
    "Article",
    "ArticlePosting",
    "Posting",
    "Thread",
    "Ticker",
    "TickerPosting",
    "Topic",
    "User",
    "type_registry",
    "events",
    "utils",
    "select",
)

from sqlalchemy import select

from . import events
from . import utils
from .api import DerStandardAPI, ReadOnlySessionError
from .types import (
    Article,
    ArticlePosting,
    Posting,
    Thread,
    Ticker,
    TickerPosting,
    Topic,
    User,
    type_registry,
)
from .webapi import Ressort, WebAPI
