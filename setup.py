#!/usr/bin/env python
#
# Copyright 2021 Basislager Services
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

"""Setup for Basislager Services."""


import os
from distutils.core import setup


with open(os.path.join(os.path.dirname(__file__), "requirements.txt")) as fp:
    requirements = [r.strip() for r in fp.readlines()]


setup(
    name="dstclient",
    version="0.3.0",
    description="API implementation for derstandard.at",
    author="Basislager Services",
    author_email="services@basislager.space",
    url="https://basislager.space",
    packages=["dstclient"],
    package_data={"dstclient": ["py.typed", "schema.graphql"]},
    install_requires=requirements,
)
