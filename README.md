# dstclient - API for derstandard.at


API implementation for crawling the news website [Der Standard](derstandard.at).

Use it with caution.
Admins will hate you for it.


## Installation

```
pip install git+https://github.com/basislagerservices/dstclient
```

## Usage

The most convenient way to access API functions is with the `DerStandardAPI` class.
This interface requires a database where results are stored automatically.

### Web API

This example shows how the web API is used to download all postings in a live ticker.

```python
from dstclient import DerStandardAPI, utils


async def main():
    engine = await utils.sqlite_engine("/tmp/database.db")
    api = DerStandardAPI(engine)

    async with api.web() as web:
        ticker = await web.get_ticker(1336696633613)
        threads = await web.get_ticker_threads(ticker)
        postings = []
        for thread in threads:
            threadpostings = await web.get_thread_postings(thread)
            postings.append(threadpostings)
```

The web API without a database interface is available as the `WebAPI` class.


### Database API

[SQLAlchemy](https://www.sqlalchemy.org/) is used as the ORM for the database.
All types returned by the web API are SQLAlchemy types.

The unified API can be used to access the database.
`DerStandardAPI.db()` returns a database session.

This example shows how all users in the database can be retrieved.
See the SQLALchemy documentation for more details.

```python
from dstclient import DerStandardAPI, User, utils

async def main():
    engine = await utils.sqlite_engine("/tmp/database.db")
    api = DerStandardAPI(engine)

    async with api.db() as s:
        users = (await s.execute(select(User))).scalars().all()
```


By default, the returned session is restricted so that the database is not modified.
Commits are not allowed and the database is rolled back after the session.
Pass the `readonly=False` flag if this is not desired.
