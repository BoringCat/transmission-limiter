import os
import logging
__log_level_map = logging.getLevelNamesMapping()

LOG_LEVEL = __log_level_map.get(os.environ.get('LOG_LEVEL', 'INFO').upper(), logging.INFO)
CONFIG_FILE = os.environ.get('CONFIG_FILE', '') or '/app/config/config.yml'

__all__ = ['LOG_LEVEL', 'CONFIG_FILE']