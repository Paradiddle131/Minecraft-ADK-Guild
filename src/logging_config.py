"""
Logging configuration for Minecraft Multi-Agent system using structlog
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

import structlog
from structlog.processors import (
    TimeStamper,
    add_log_level,
    dict_tracebacks,
)
from structlog.stdlib import (
    BoundLogger,
    LoggerFactory,
    add_logger_name,
    filter_by_level,
)


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_dir: str = "logs",
    console_output: bool = True,
    json_format: bool = False,
) -> None:
    """
    Configure structlog for both console and file output
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional specific log file name. If None, generates timestamp-based name
        log_dir: Directory for log files (default: "logs")
        console_output: Whether to output to console (default: True)
        json_format: Whether to use JSON format for logs (default: False for console readability)
    """
    # Create logs directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Generate log file name if not provided
    if log_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"minecraft_agent_{timestamp}.log"
    
    full_log_path = log_path / log_file
    
    # Configure Python stdlib logging
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # File handler - always use JSON format for easier parsing
    file_handler = logging.FileHandler(full_log_path, encoding='utf-8')
    file_handler.setLevel(getattr(logging, log_level.upper()))
    file_formatter = logging.Formatter("%(message)s")  # structlog will format
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Structlog processors
    timestamper = TimeStamper(fmt="iso")
    
    shared_processors = [
        add_log_level,
        add_logger_name,
        timestamper,
        structlog.processors.CallsiteParameterAdder(
            parameters=[
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.LINENO,
                structlog.processors.CallsiteParameter.FUNC_NAME,
            ]
        ),
        dict_tracebacks,
    ]
    
    # Console renderer - pretty print for development
    if json_format or not console_output:
        console_renderer = structlog.processors.JSONRenderer()
    else:
        console_renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            pad_event=30,
        )
    
    # File renderer - always JSON for structured logging
    file_renderer = structlog.processors.JSONRenderer()
    
    # Configure structlog
    structlog.configure(
        processors=[
            filter_by_level,
            *shared_processors,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Set up ProcessorFormatter for each handler
    # Console gets pretty output
    if console_output:
        console_processor = structlog.stdlib.ProcessorFormatter(
            processor=console_renderer,
            foreign_pre_chain=shared_processors,
        )
        console_handler.setFormatter(console_processor)
    
    # File gets JSON output
    file_processor = structlog.stdlib.ProcessorFormatter(
        processor=file_renderer,
        foreign_pre_chain=shared_processors,
    )
    file_handler.setFormatter(file_processor)
    
    # Log initialization
    logger = structlog.get_logger(__name__)
    logger.info(
        "Logging initialized",
        log_level=log_level,
        log_file=str(full_log_path),
        console_output=console_output,
        json_format=json_format,
    )


def get_logger(name: str) -> BoundLogger:
    """
    Get a configured structlog logger
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured structlog BoundLogger
    """
    return structlog.get_logger(name)