#
# Copyright 2023 Basislager Services
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

"""Database events for sanitation."""

from typing import Any

from sqlalchemy import Engine, event
from sqlalchemy.orm import Session

from .types import Article, Ticker, Topic


@event.listens_for(Engine, "connect")
def pragma_foreign_keys(connection: Any, connection_record: Any) -> None:
    """Set the foreign_keys pragma to check for nonexisting foreign keys."""
    # TODO: Is there a better way?
    if hasattr(connection.dbapi, "sqlite"):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
