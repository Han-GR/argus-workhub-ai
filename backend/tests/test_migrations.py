"""首次启动使用已提交的迁移，且不会向源码目录生成迁移文件。"""

import sqlalchemy as sa
from fastapi.testclient import TestClient

from app.config.path_conf import ALEMBIC_VERSION_DIR
from app.config.setting import settings


def test_bootstrap_matches_metadata(test_client: TestClient, versions_before_layout: frozenset[str]) -> None:
    assert {p.name for p in ALEMBIC_VERSION_DIR.glob("*.py")} == versions_before_layout
    engine = sa.create_engine(settings.DB_URI)
    try:
        with engine.connect() as connection:
            assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == "argus_initial"
    finally:
        engine.dispose()
