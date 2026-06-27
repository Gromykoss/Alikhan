#!/bin/sh
set -e
echo "Using prisma db push instead of migrate deploy..."
cd /evolution-api
npx prisma db push --schema ./prisma/mysql-schema.prisma --accept-data-loss --force-reset || npx prisma db push --schema ./prisma/mysql-schema.prisma --accept-data-loss
exec node dist/main.js