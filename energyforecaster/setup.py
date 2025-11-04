"""
Setup configuration for Energy Demand Forecaster package
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="energy-demand-forecaster",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A comprehensive module for electricity demand forecasting",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/energy-demand-forecaster",
    py_modules=["energy_demand_forecaster"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.7",
    install_requires=requirements,
    extras_require={
        "prophet": ["prophet>=1.1.0"],
        "deep-learning": ["tensorflow>=2.8.0", "keras>=2.8.0"],
        "xgboost": ["xgboost>=1.5.0"],
        "lightgbm": ["lightgbm>=3.3.0"],
        "all": [
            "prophet>=1.1.0",
            "tensorflow>=2.8.0",
            "keras>=2.8.0",
            "xgboost>=1.5.0",
            "lightgbm>=3.3.0",
        ],
    },
    keywords="forecasting time-series energy electricity demand prediction machine-learning",
)
