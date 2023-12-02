#
# Copyright 2021-2022 Basislager Services
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

"""Configuration and fixtures for unit tests."""

import contextlib
import json
import subprocess as sp
import socket
import time

import pytest

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from dstclient import *


@pytest.fixture(scope="session")
def docker_mariadb():
    """Run a MariaDB instance in a Docker container.

    Returns the IP address of the instance.
    """
    container = sp.Popen(
        [
            "docker",
            "run",
            "--name",
            "dstclient-mariadb",
            "--rm",
            "--env",
            "MARIADB_ALLOW_EMPTY_ROOT_PASSWORD=1",
            "--env",
            "MARIADB_DATABASE=dstclient",
            "mariadb:latest",
        ],
        stdout=sp.DEVNULL,
        stderr=sp.DEVNULL,
    )

    # Poll until the database becomes available.
    for _ in range(32):
        result = sp.run(["docker", "inspect", "dstclient-mariadb"], capture_output=True)
        entries = json.loads(result.stdout)
        if entries:
            host = entries[0]["NetworkSettings"]["IPAddress"]
            with contextlib.suppress(TimeoutError, ConnectionRefusedError):
                s = socket.socket()
                s.settimeout(0.5)
                s.connect((host, 3306))
                s.close()
                break

        time.sleep(0.5)

    yield host

    sp.run(["docker", "stop", "dstclient-mariadb"], capture_output=True)
    container.wait()


@pytest.fixture
async def mariadb_engine(docker_mariadb):
    """Create engine for the empty MariaDB database."""
    engine = await utils.mysql_engine("dstclient", host=docker_mariadb)
    async with engine.begin() as conn:
        await conn.run_sync(type_registry.metadata.drop_all)
        await conn.run_sync(type_registry.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def sqlite_engine(tmp_path):
    """Create engine for empty SQLite database."""
    engine = await utils.sqlite_engine(f"{tmp_path}/db")

    yield engine

    await engine.dispose()


@pytest.fixture(params=[None, "sqlite", "mariadb"])
async def engine_none(request, mariadb_engine, sqlite_engine):
    """Parametrized fixture for supported engines, including None."""
    if request.param is None:
        return None
    elif request.param == "sqlite":
        return sqlite_engine
    elif request.param == "mariadb":
        return mariadb_engine

    raise Exception("unexpected engine parameter")


@pytest.fixture(params=["sqlite", "mariadb"])
async def engine(request, mariadb_engine, sqlite_engine):
    """Parametrized fixture for supported engines."""
    if request.param == "sqlite":
        return sqlite_engine
    elif request.param == "mariadb":
        return mariadb_engine

    raise Exception("unexpected engine parameter")
