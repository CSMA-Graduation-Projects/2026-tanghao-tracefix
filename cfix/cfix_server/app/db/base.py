"""ORM 基类模块，负责数据库基础设施与连接管理。"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
