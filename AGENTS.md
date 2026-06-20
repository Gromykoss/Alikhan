# Alikhan — рабочая среда Hermes

Проект: WhatsApp AI-агент на n8n + evolution-api + xAI.
Репозиторий: https://github.com/Gromykoss/Alikhan

## Быстрые команды

```bash
# Статус всех контейнеров
docker ps --filter "name=evolution" --filter "name=n8n"

# Логи
docker logs evolution-api --tail 30
docker logs n8n --tail 30

# Рестарт
docker restart evolution-api evolution-postgres evolution-redis

# Дамп БД n8n
docker cp n8n:/home/node/.n8n/database.sqlite /tmp/n8n_db.sqlite
sqlite3 /tmp/n8n_db.sqlite ".tables"

# Работа с воркфлоу через БД
python3 -c "
import sqlite3
db = sqlite3.connect('/tmp/n8n_db.sqlite')
db.row_factory = sqlite3.Row
for w in db.execute('SELECT id, name, active FROM workflow_entity').fetchall():
    print(dict(w))
"
```
