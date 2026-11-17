from sqlalchemy import BigInteger, Integer
from src.core.database import Base

# Portable 64-bit integer type:
# In PostgreSQL: BIGINT (64-bit signed integer)
# In SQLite: INTEGER (64-bit signed integer that enables SQLite's AUTOINCREMENT rowid)
BigIntID = BigInteger().with_variant(Integer, "sqlite")

__all__ = ["Base", "BigIntID"]
