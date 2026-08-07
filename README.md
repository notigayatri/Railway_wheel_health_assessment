# Railway Wheel Health Assessment

An AI-powered railway wheel inspection system that detects wheel defects, assesses defect severity, and maintains a Digital Wheel Health Record for every inspected wheel.

## Features

- Defect Detection using YOLO
- Severity Assessment
- Digital Wheel Health Record
- Inspection History Tracking
- Dashboard Statistics
- SQLite-based Data Storage

## Project Structure

```
Railway_wheel_health_assessment/

core/
│
└── wheel_lifecycle/
    ├── database.py
    ├── repository.py
    ├── dashboard.py
    ├── history.py
    ├── id_generator.py
    └── models.py

database/

tests/

detection/

severity/
```

## Tech Stack

- Python 3
- SQLite
- FastAPI *(API integration - upcoming)*
- YOLO (Ultralytics)
- OpenCV

## Current Progress

- ✅ Defect Detection
- ✅ Severity Assessment
- ✅ Digital Wheel Health Record Backend
- ✅ Inspection History
- ✅ Dashboard Statistics
- ⏳ FastAPI Integration
- ⏳ Frontend UI

## Team Modules

| Module | Status |
|---------|--------|
| Defect Detection | Completed |
| Severity Assessment | Completed |
| Digital Wheel Health Record | Completed |
| Reliability Estimation | In Progress |
| Explainable AI | In Progress |
| Maintenance Prioritization | In Progress |

## Running Tests

```bash
python -m tests.test_database
python -m tests.test_repository
python -m tests.test_history
python -m tests.test_dashboard
```

## License

Academic Final Year Project


## Latest Update

- Migrated Digital Wheel Health Record from JSON storage to SQLite.
- Added Repository Layer.
- Added Dashboard Statistics.
- Added Inspection History.
- Added Backend Test Suite.