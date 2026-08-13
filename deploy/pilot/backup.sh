#!/bin/sh
set -eu

: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET="/backups/$STAMP"
mkdir -p "$TARGET"

pg_dump \
  -Fc \
  -h postgres \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  > "$TARGET/database.dump"

tar -czf "$TARGET/storage.tar.gz" -C /storage .

SCHEMA_HEAD="$({
  psql \
    -At \
    -h postgres \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    -c "SELECT version_num FROM alembic_version LIMIT 1"
} 2>/dev/null || printf 'unknown')"

cat > "$TARGET/manifest.txt" <<EOF
timestamp=$STAMP
app_version=${APP_VERSION:-unknown}
schema_head=$SCHEMA_HEAD
EOF

printf 'Pilot backup created: %s\n' "$TARGET"
