"""
============================================================
Sentinel Data Engine
Global Settings
============================================================
"""

from pathlib import Path

# ============================================================
# Project
# ============================================================

PROJECT_NAME = "Sentinel Data Engine"

VERSION = "1.0.0"

DEBUG = True

# ============================================================
# Paths
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

CONTRACTS_DIR = BASE_DIR / "contracts"

DATASETS_DIR = BASE_DIR / "datasets"

RAW_DATASET_DIR = DATASETS_DIR / "raw"

PROCESSED_DATASET_DIR = DATASETS_DIR / "processed"

TRAINING_DATASET_DIR = DATASETS_DIR / "training"

LOG_DIR = BASE_DIR / "logs"

# ============================================================
# Simulation
# ============================================================

SIMULATION_DAYS = 365

TIME_STEP_SECONDS = 30

TOTAL_SITES = 1

TOTAL_ZONES = 4

TOTAL_WORKERS = 50

TOTAL_MACHINES = 20

# ============================================================
# Database
# ============================================================

DB_HOST = "localhost"

DB_PORT = 5432

DB_NAME = "sentinel"

DB_USER = "postgres"

DB_PASSWORD = "postgres"

# ============================================================
# Random Seed
# ============================================================

RANDOM_SEED = 42