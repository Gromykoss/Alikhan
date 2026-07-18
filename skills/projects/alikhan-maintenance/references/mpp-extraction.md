# MPP Extraction — Complete Workflow

**Status 2026-07-01:** MPP — проприетарный бинарный формат Microsoft Project (OLE2 container). Полное извлечение задач с датами требует Java-стека.

## Что работает (без Java)

1. **Скачать MPP из WhatsApp:**
```python
# Evolution API — получить base64
payload = json.dumps({"message": {"key": {"id": msg_id}}}).encode()
req = Request(f"{EVO}/chat/getBase64FromMediaMessage/alikhan", ...)
b64 = json.loads(resp.read().decode()).get("base64", "")
```

2. **Прочитать метаданные через olefile:**
```python
import olefile
ole = olefile.OleFileIO(tmppath)

# Список стримов
ole.listdir()
# → ['   114', 'TBkndTask', 'Var2Data'] (задачи)
# → ['   114', 'TBkndRsc', 'Var2Data']  (ресурсы)
# → ['Props14']  (название проекта, автор, путь к файлу)

# Название проекта из Props14:
props14 = ole.openstream('Props14').read()
# UTF-16LE, фильтр Cyrillic
```

3. **Текст через strings:**
```bash
strings -e l file.mpp  # UTF-16LE — НЕ работает для MPP (кастомное кодирование)
```

## Что НЕ работает без Java

- Имена задач (TBkndTask/Var2Data — MPP custom variable-length encoding, не чистый UTF-16LE)
- Даты начала/окончания (TBkndTask/FixedData — MPP internal date format, не OLE date)
- Длительности, зависимости, назначения ресурсов, % выполнения

## Полный стек (требуется)

```bash
# Установка (200+ MB)
apt install openjdk-21-jdk
pip install mpxj jpype1

# Код (через Jpype)
import jpype, glob
jars = glob.glob('.../mpxj/lib/*.jar')
jpype.startJVM(classpath=':'.join(jars))
UniversalProjectReader = jpype.JClass('net.sf.mpxj.reader.UniversalProjectReader')
project = UniversalProjectReader().read(path)

for task in project.getAllTasks():
    name = task.getName()
    start = task.getStart()   # java.util.Date
    finish = task.getFinish()
    dur = task.getDuration()
    level = task.getOutlineLevel()
```

**Проблема 2026-07-01:** Jpype не смог найти классы (classpath issue). JRE есть, JDK нет. Без javac нельзя скомпилировать Java-обёртку. Решение: установить JDK или найти standalone MPP→CSV конвертер.

## Эволюция попыток

| Попытка | Инструмент | Результат |
|---------|-----------|-----------|
| 1 | openpyxl | BadZipFile — не Excel |
| 2 | document_extractor :8099 | Только метаданные (65 chars) |
| 3 | LibreOffice --convert-to csv | "source file could not be loaded" |
| 4 | olefile + Var2Data regex | 1989 фрагментов, только 3 полных строки |
| 5 | strings -e l | 0 Cyrillic strings |
| 6 | mpxj + jpype | ClassNotFoundException |
| 7 | Java --class-path (single-file) | compilation failed (JRE only, no javac) |
| 8 | LibreOffice --convert-to xlsx | Same — can't load .mpp |
