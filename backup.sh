#!/bin/bash
# Backup script for NDK Dashboard
# Creates timestamped folder backups and keeps only the last 5

set -e

SOURCE_DIR="/home/nutanix/dev/ndk-dashboard"
BACKUP_BASE_DIR="/home/nutanix/dev/backups"
BACKUP_DIR="${BACKUP_BASE_DIR}/ndk-dashboard"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="ndk-dashboard_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"
MAX_BACKUPS=5

echo "=========================================="
echo "NDK Dashboard Backup Script"
echo "=========================================="
echo ""

# Create backup directory if it doesn't exist
if [ ! -d "${BACKUP_DIR}" ]; then
    echo "Creating backup directory: ${BACKUP_DIR}"
    mkdir -p "${BACKUP_DIR}"
    echo "✓ Backup directory created"
fi

echo "Source: ${SOURCE_DIR}"
echo "Backup: ${BACKUP_PATH}"
echo ""

# Create the backup (exclude venv, __pycache__, .git, logs, and other temporary files)
echo "Creating backup..."
rsync -a \
    --exclude='.venv' \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='*.log' \
    --exclude='.env' \
    --exclude='.pytest_cache' \
    --exclude='node_modules' \
    --exclude='.DS_Store' \
    "${SOURCE_DIR}/" "${BACKUP_PATH}/"

# Check if backup was created successfully
if [ -d "${BACKUP_PATH}" ]; then
    BACKUP_SIZE=$(du -sh "${BACKUP_PATH}" | cut -f1)
    echo "✓ Backup created successfully: ${BACKUP_NAME} (${BACKUP_SIZE})"
else
    echo "✗ Failed to create backup"
    exit 1
fi

echo ""
echo "Cleaning up old backups (keeping last ${MAX_BACKUPS})..."

# Count current backups
BACKUP_COUNT=$(find "${BACKUP_DIR}" -maxdepth 1 -type d -name "ndk-dashboard_*" 2>/dev/null | wc -l)
echo "Current backup count: ${BACKUP_COUNT}"

# Remove old backups if we have more than MAX_BACKUPS
if [ ${BACKUP_COUNT} -gt ${MAX_BACKUPS} ]; then
    BACKUPS_TO_DELETE=$((BACKUP_COUNT - MAX_BACKUPS))
    echo "Removing ${BACKUPS_TO_DELETE} old backup(s)..."
    
    # List backups sorted by time (oldest first) and delete the excess
    find "${BACKUP_DIR}" -maxdepth 1 -type d -name "ndk-dashboard_*" | sort | head -n ${BACKUPS_TO_DELETE} | while read backup; do
        echo "  Deleting: $(basename ${backup})"
        rm -rf "${backup}"
    done
    
    echo "✓ Old backups removed"
else
    echo "✓ No cleanup needed"
fi

echo ""
echo "=========================================="
echo "Backup Summary"
echo "=========================================="
echo "Latest backup: ${BACKUP_NAME}"
echo "Backup location: ${BACKUP_DIR}"
echo ""
echo "Available backups:"
find "${BACKUP_DIR}" -maxdepth 1 -type d -name "ndk-dashboard_*" 2>/dev/null | sort -r | while read backup; do
    SIZE=$(du -sh "${backup}" | cut -f1)
    echo "  $(basename ${backup}) (${SIZE})"
done
echo ""
echo "Total backups: $(find "${BACKUP_DIR}" -maxdepth 1 -type d -name "ndk-dashboard_*" 2>/dev/null | wc -l)"
echo ""
echo "To access a backup:"
echo "  cd ${BACKUP_PATH}"
echo ""