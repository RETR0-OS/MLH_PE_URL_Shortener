#!/usr/bin/env bash
# PostgreSQL backup / restore helper.
# Usage:
#   ./scripts/pg_backup.sh backup            # creates timestamped dump
#   ./scripts/pg_backup.sh restore <file>    # restores from dump
#   ./scripts/pg_backup.sh list              # list existing backups
set -euo pipefail

BACKUP_DIR="./backups"
DB_SERVICE="postgres"
DB_NAME="${POSTGRES_DB:-hackathon_db}"
DB_USER="${POSTGRES_USER:-postgres}"
COMPOSE="docker compose"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

backup() {
    local file="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz"
    echo "📦  Backing up $DB_NAME → $file"
    $COMPOSE exec -T "$DB_SERVICE" \
        pg_dump -U "$DB_USER" -d "$DB_NAME" --no-owner --no-acl \
        | gzip > "$file"
    local size
    size=$(du -h "$file" | cut -f1)
    echo "✅  Backup complete ($size)"

    # Prune backups older than 7 days
    find "$BACKUP_DIR" -name "*.sql.gz" -mtime +7 -delete 2>/dev/null || true
    echo "🗑   Old backups (>7d) pruned"
}

restore() {
    local file="${1:?Usage: $0 restore <file>}"
    if [[ ! -f "$file" ]]; then
        echo "❌  File not found: $file" && exit 1
    fi
    echo "⚠️   Restoring $DB_NAME from $file (this will overwrite current data)"
    read -rp "Continue? [y/N] " confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

    gunzip -c "$file" | $COMPOSE exec -T "$DB_SERVICE" \
        psql -U "$DB_USER" -d "$DB_NAME" --quiet
    echo "✅  Restore complete"
}

list_backups() {
    echo "Available backups:"
    ls -lh "$BACKUP_DIR"/*.sql.gz 2>/dev/null || echo "(none)"
}

case "${1:-backup}" in
    backup)  backup ;;
    restore) restore "${2:-}" ;;
    list)    list_backups ;;
    *)       echo "Usage: $0 {backup|restore <file>|list}" && exit 1 ;;
esac
