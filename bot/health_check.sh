#!/bin/bash
# Alikhan Health Check Script
# Usage: bash health_check.sh

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

PASS=0
FAIL=0

check() {
    local name="$1"
    local cmd="$2"
    local expected="$3"
    
    echo -n "Checking $name... "
    if eval "$cmd" >/dev/null 2>&1; then
        echo -e "${GREEN}✅${NC} $expected"
        ((PASS++))
    else
        echo -e "${RED}❌${NC} FAILED"
        ((FAIL++))
    fi
}

echo "=== Alikhan Infrastructure Health Check ==="
echo

# 1. Bot process
echo -n "1. Bot process (main_waha.py): "
if pid=$(pgrep -af 'main_waha.py' | head -1); then
    echo -e "${GREEN}✅${NC} PID: $(echo "$pid" | awk '{print $1}')"
    ((PASS++))
else
    echo -e "${RED}❌${NC} No process found"
    ((FAIL++))
fi

# 2. Evolution API
echo -n "2. Evolution API (http://127.0.0.1:8080/): "
if status=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/); then
    if [ "$status" = "200" ]; then
        echo -e "${GREEN}✅${NC} Status 200"
        ((PASS++))
    else
        echo -e "${RED}❌${NC} Status $status"
        ((FAIL++))
    fi
else
    echo -e "${RED}❌${NC} Connection failed"
    ((FAIL++))
fi

# 3. PostgreSQL container
echo -n "3. PostgreSQL (evolution-postgres): "
if docker inspect evolution-postgres --format='{{.State.Status}}' 2>/dev/null | grep -q "running"; then
    echo -e "${GREEN}✅${NC} Running"
    ((PASS++))
else
    echo -e "${RED}❌${NC} Not running"
    ((FAIL++))
fi

# 4. DB connection
echo -n "4. DB connection (psycopg2): "
if python3 -c "
import psycopg2
conn = psycopg2.connect(host='172.22.0.2', dbname='evolution_db', user='evolution', password='pass123', port=5432)
conn.close()
print('OK')
" 2>/dev/null; then
    echo -e "${GREEN}✅${NC} OK"
    ((PASS++))
else
    echo -e "${RED}❌${NC} Connection failed"
    ((FAIL++))
fi

# 5. Template
echo -n "5. EJO Template (templates/ЕЖО_шаблон.xlsx): "
if [ -f "templates/ЕЖО_шаблон.xlsx" ]; then
    size=$(stat -c%s "templates/ЕЖО_шаблон.xlsx")
    echo -e "${GREEN}✅${NC} Exists, size: $size bytes"
    ((PASS++))
else
    echo -e "${RED}❌${NC} Not found"
    ((FAIL++))
fi

# 6. Document extractor
echo -n "6. Document extractor (http://127.0.0.1:8099/health): "
if response=$(curl -s http://127.0.0.1:8099/health); then
    if echo "$response" | grep -qi "ok"; then
        echo -e "${GREEN}✅${NC} OK"
        ((PASS++))
    else
        echo -e "${RED}❌${NC} Unexpected: $response"
        ((FAIL++))
    fi
else
    echo -e "${RED}❌${NC} Connection failed"
    ((FAIL++))
fi

# 7. Last EJO
echo -n "7. Last EJO file (/tmp/ЕЖО_*_v*.xlsx): "
if last=$(ls -lt /tmp/ЕЖО_*_v*.xlsx 2>/dev/null | head -1); then
    path=$(echo "$last" | awk '{print $NF}')
    date=$(echo "$last" | awk '{print $6, $7, $8}')
    echo -e "${GREEN}✅${NC} $path ($date)"
    ((PASS++))
else
    echo -e "${RED}❌${NC} No EJO files found"
    ((FAIL++))
fi

# 8. Bot log tail (no ERROR/Exception)
echo -n "8. Bot log tail (bot/bot.log): "
if tail -5 bot.log 2>/dev/null | grep -qiE "error|exception"; then
    echo -e "${RED}❌${NC} Errors found in tail"
    ((FAIL++))
else
    echo -e "${GREEN}✅${NC} No ERROR/Exception in last 5 lines"
    ((PASS++))
fi

echo
echo "=== Summary ==="
echo -e "Passed: ${GREEN}$PASS${NC} | Failed: ${RED}$FAIL${NC}"

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}All checks passed!${NC}"
    exit 0
else
    echo -e "${RED}Some checks failed.${NC}"
    exit 1
fi
