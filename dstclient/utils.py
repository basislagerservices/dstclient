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

"""Utils for other modules."""

__all__ = ("chromedriver", "sqlite_engine", "mysql_engine")

import contextlib
from typing import Iterator

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromiumService

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType

from .types import type_registry


@contextlib.contextmanager
def chromedriver() -> Iterator[webdriver.Chrome]:
    """Create a webdriver for Chrome."""
    try:
        options = Options()
        options.add_argument("--no-sandbox")  # type: ignore
        options.add_argument("--headless")  # type: ignore
        options.add_argument("--disable-gpu")  # type: ignore
        options.add_argument("--disable-dev-shm-usage")  # type: ignore
        options.add_argument("--window-size=1920,1080")  # type: ignore

        driver = webdriver.Chrome(
            service=ChromiumService(
                ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()
            ),
            options=options,
        )
        driver.implicitly_wait(10)

        yield driver
    finally:
        driver.quit()


async def sqlite_engine(database: str) -> AsyncEngine:
    """Create an asynchronous engine for the given database path."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{database}")
    async with engine.begin() as conn:
        await conn.run_sync(type_registry.metadata.create_all)
    return engine


async def mysql_engine(
    dbname: str,
    host: str = "127.0.0.1",
    user: str = "root",
    password: str = "",
    port: int = 3306,
) -> AsyncEngine:
    """Create an asynchronous engine for a MySQL or MariaDB database."""
    connstr = (
        f"mysql+aiomysql://{user}:{password}@{host}:{port}/{dbname}?charset=utf8mb4"
    )
    engine = create_async_engine(connstr)
    async with engine.begin() as conn:
        await conn.run_sync(type_registry.metadata.create_all)
    return engine
