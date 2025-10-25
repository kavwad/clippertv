#!/usr/bin/env python3
"""One-shot ingestion script for systemd timer."""

import sys

from .service import run_monthly_ingestion, setup_logging


def main():
    logger = setup_logging()
    logger.info("Starting one-shot monthly ingestion")

    try:
        run_monthly_ingestion()
        logger.info("One-shot ingestion completed")
        return 0
    except Exception as e:
        logger.error(f"One-shot ingestion failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
