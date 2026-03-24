import itertools
import structlog

from alembic import context
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from sqlalchemy.exc import OperationalError

from app.db.models import Base
from app.settings import DATABASE_URL

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
# Alembic requires a sync driver; replace asyncpg with psycopg2 for migrations
sync_database_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
config.set_main_option('sqlalchemy.url', sync_database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
logger = structlog.get_logger(__name__)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

MAX_RETRIES = 600 # retry for ~10 minutes

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
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
            include_schemas=True,
            compare_server_default=True,
            include_object=include_object,
        )

        for attempt in itertools.count(start=1):
            try:
                with context.begin_transaction():
                    context.run_migrations()
                break
            except OperationalError as e:
                if attempt >= MAX_RETRIES:
                    raise e # noqa: TRY201
                if 'psycopg2.errors.LockNotAvailable' in str(e):
                    logger.info(f'migration attempt #{attempt} failed, retrying - error: {e}')
                    continue
                raise e # noqa: TRY201


def include_object(object, name, type_, reflected, compare_to):
    # Exclude the PostGIS spatial_ref_sys table from migrations
    return not (type_ == 'table' and name == 'spatial_ref_sys')


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
