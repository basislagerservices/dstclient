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

"""Utils for other modules."""

import contextlib
from typing import Iterator

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


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

        driver = webdriver.Chrome(options=options)
        driver.implicitly_wait(10)

        yield driver
    finally:
        driver.quit()
