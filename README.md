# ЛР5 — стабильность агента и сбои инструментов

Работа использует ReAct ЛР4, AgentDojo workspace и banking v1.2.2. Для показа готовых измерений модель не нужна.

В Windows PowerShell с Python 3.12:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-demo.txt
.\.venv\Scripts\python.exe prepare_laptop.py
Start-Process .\report.pdf
.\.venv\Scripts\mlflow.exe ui --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1 --port 5004
```

Откройте http://127.0.0.1:5004, Model training → lr5. В MLflow три названия метрик: success, mean_input_tokens, duplicate_writes. В запуске t0_r0 → Artifacts находятся общие кривые pass^k и pass@k, график сбоев/переноса, таблицы, оценка 15 ответов и трейсы.

results.jsonl содержит 316 основных и 20 отладочных эпизодов. schedule.json хранит полный план запусков. Промпты и базовый цикл перенесены из ЛР4 с проверкой хешей. Прогноз и конфигурация зафиксированы до измерений.

Проверка готовых результатов: python verify_results.py. Для проверки формул: python metrics.py. Для тестов сбоев: установить requirements.txt, затем python -m unittest -v test_faults. Тесты не вызывают языковую модель.

success — доля успешных эпизодов; mean_input_tokens — средняя сумма входных токенов за весь эпизод; duplicate_writes — суммарное число повторных исполнений записей. В каждом запуске в traces лежат только его эпизоды, общие графики и отчёт записаны однократно в t0_r0.

Для новых измерений требуется сервер ЛР4 по адресу из config.json и установка requirements.txt. Используйте отдельную копию с пустыми traces и results.jsonl, сохранив исходный результат. run.py проверяет хеши frozen.json и запускает только отсутствующие ключи. Незавершённые трейсы требуют проверки перед повтором. analyze.py считает метрики и формирует выборку 15 ответов. Содержательная оценка хранится в analysis/audit.json, разбор эпизодов — analysis/case_reviews.json. report.py собирает четырёхстраничный PDF.

Проверка восстановления сервиса: при fault_p=1 гарантируется первый контролируемый сбой A, после него сервис восстанавливается. При постоянно недоступном сервисе и fault_p=1 все три попытки ошибочны — это отдельный тест. Основные измерения используют случайный сбой на каждой попытке, включая автоматические повторы.
