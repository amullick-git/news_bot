"""
Utilities
=========

Common utility functions used across the application.
Currently primarily handles logging configuration.
"""
import logging
import sys

def setup_logging(level=logging.INFO):
    """
    Configure structured logging.
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
