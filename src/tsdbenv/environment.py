"""Load local environment configuration for the tsdbenv CLI."""

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def load_environment(directory: Optional[Path] = None) -> bool:
    """Load ``.env`` from the working directory without overriding exported values."""
    base_directory = directory if directory is not None else Path.cwd()
    return load_dotenv(dotenv_path=base_directory / ".env", override=False)
