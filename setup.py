# Author: Wagner Bianchi <wagnerbianchijr@gmail.com>
# Created: 2026-08-19

from setuptools import find_packages, setup

setup(
    name="tsdbenv",
    version="1.1.0",
    author="Wagner Bianchi",
    author_email="wagnerbianchijr@gmail.com",
    description="PostgreSQL + TimescaleDB environment manager via Docker",
    url="https://github.com/wagnerbianchijr/tsdbenv.git",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.10",
    install_requires=[
        "pydantic>=2.0",
        "click>=8.1",
        "python-dotenv>=1.0",
        "docker>=6.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "flake8>=6.0",
            "mypy>=1.0",
            "black>=23.0",
            "isort>=5.0",
            "pylint>=3.0",
            "bandit>=1.7",
        ]
    },
    entry_points={
        "console_scripts": [
            "tsdbenv=tsdbenv.cli:main",
        ]
    },
)
