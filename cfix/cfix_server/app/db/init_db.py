from app.db.sess import engine
from app.db.base import Base
from app import models  # noqa: F401
from app.core.log import get_logger

logger = get_logger("init_db")


def main():
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表初始化完成")


if __name__ == "__main__":
    main()
