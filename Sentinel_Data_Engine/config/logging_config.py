"""
Logging Configuration
"""

import logging

from pathlib import Path

from config.settings import LOG_DIR


LOG_DIR.mkdir(

    parents=True,

    exist_ok=True

)


logging.basicConfig(

    level=logging.INFO,

    format="%(asctime)s | %(levelname)s | %(message)s",

    handlers=[

        logging.FileHandler(

            Path(LOG_DIR) / "engine.log"

        ),

        logging.StreamHandler()

    ]

)

logger = logging.getLogger("SentinelDataEngine")