"""
============================================================
Sentinel Data Engine
Global Settings
============================================================
"""

from pathlib import Path
import os

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
# Phase 3 remediation note (SENTINEL forensic audit, security baseline):
# these were previously hardcoded literals, including a literal password.
# Moved to environment variables with the same local-dev values as
# defaults, so nothing about local/demo behavior changes, but a real
# deployment is no longer forced to use (or silently inherit) this
# literal credential -- it can override via env vars instead.

DB_HOST = os.environ.get("SENTINEL_DB_HOST", "localhost")

DB_PORT = int(os.environ.get("SENTINEL_DB_PORT", "5432"))

DB_NAME = os.environ.get("SENTINEL_DB_NAME", "sentinel")

DB_USER = os.environ.get("SENTINEL_DB_USER", "postgres")

DB_PASSWORD = os.environ.get("SENTINEL_DB_PASSWORD", "postgres")

# ============================================================
# Random Seed
# ============================================================

RANDOM_SEED = 42