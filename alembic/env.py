from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import get_settings
from app.database import models  # noqa: F401
from app.database.base import Base
from app.modules.comments import models as comment_models  # noqa: F401
from app.modules.contracts import models as contract_models  # noqa: F401
from app.modules.expertises import models as expertise_models  # noqa: F401
from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.import_ import models as import_models  # noqa: F401
from app.modules.organizations import models as organization_models  # noqa: F401
from app.modules.tasks import models as task_models  # noqa: F401
from app.modules.workflows import models as workflow_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.effective_database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.effective_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
