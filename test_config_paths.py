"""
Test script to verify config paths are correctly set up
"""

import sys
import config

print("=" * 70)
print("TRADER LEDGER - Configuration Paths Test")
print("=" * 70)
print()
print(f"Running as frozen (packaged .exe): {getattr(sys, 'frozen', False)}")
print()
print("Directory Paths:")
print(f"  BASE_DIR:       {config.BASE_DIR}")
print(f"  DATA_DIR:       {config.DATA_DIR}")
print(f"  LOGS_DIR:       {config.LOGS_DIR}")
print(f"  EXPORTS_DIR:    {config.EXPORTS_DIR}")
print(f"  DB_BACKUP_DIR:  {config.DB_BACKUP_DIR}")
print()
print("File Paths:")
print(f"  DB_PATH:        {config.DB_PATH}")
print(f"  SAMPLE_CSV:     {config.SAMPLE_CSV_PATH}")
print(f"  LOG_FILE:       {config.LOG_FILE}")
print()
print("Directory Existence:")
print(f"  DATA_DIR exists:       {config.DATA_DIR.exists()}")
print(f"  LOGS_DIR exists:       {config.LOGS_DIR.exists()}")
print(f"  EXPORTS_DIR exists:    {config.EXPORTS_DIR.exists()}")
print(f"  DB_BACKUP_DIR exists:  {config.DB_BACKUP_DIR.exists()}")
print()
print("=" * 70)
print("Expected behavior:")
print("  - Development:  DATA_DIR should be local 'data/' folder")
print("  - Production:   DATA_DIR should be C:/Users/{Username}/AppData/Roaming/TraderLedger")
print("=" * 70)
