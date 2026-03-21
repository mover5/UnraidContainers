from . import azure, mysql

# All registered backup source handlers. Add new source modules here to plug them in.
ALL_SOURCES = [mysql, azure]
