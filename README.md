# Railway Wheel Health Assessment

An AI-powered railway wheel inspection system that detects wheel defects, assesses defect severity, checks how reliable each detection is, explains why the model made its call, maintains a Digital Wheel Health Record for every inspected wheel, and ranks wheels by maintenance priority.

## Features

- Defect Detection using YOLO
- Severity Assessment (K-Means clustering)
- Reliability Estimation (Test-Time Augmentation)
- Explainable AI (Grad-CAM / EigenCAM heatmaps)
- Maintenance Priority Engine (risk scoring + ranking)
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

reliability/
    ├── augmentations.py
    └── reliability.py

explainability/
    └── gradcam.py

maintenance_priority/
    ├── config.py
    ├── trend.py
    ├── risk_engine.py
    ├── run_priority.py
    └── rank_fleet.py

models/          # best.pt (not tracked in git)

images/          # sample/test wheel images

outputs/         # annotated images, Grad-CAM heatmaps, feature CSVs
```

## Tech Stack

- Python 3
- SQLite
- FastAPI *(API integration - upcoming)*
- YOLO (Ultralytics)
- OpenCV
- PyTorch
- pytorch-grad-cam (EigenCAM)
- scikit-learn (K-Means clustering)

## Current Progress

- ✅ Defect Detection
- ✅ Severity Assessment
- ✅ Reliability Estimation (Test-Time Augmentation)
- ✅ Explainable AI (Grad-CAM)
- ✅ Maintenance Priority Engine
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
| Reliability Estimation | Completed |
| Explainable AI | Completed |
| Maintenance Prioritization | Completed |

## Running the Core Pipeline

```bash
python main.py
```

## Running the New Features

**Explainable AI (Grad-CAM heatmap):**
```bash
python explainability/gradcam.py                      # runs on the default sample image
python explainability/gradcam.py images/your_image.jpg # or any image you choose
```
Saves an annotated heatmap to `outputs/gradcam/`, showing which regions of the wheel most influenced the model's detections, with the detection boxes drawn on top.

**Reliability Estimation (Test-Time Augmentation):**
```python
from reliability.reliability import calculate_reliability
result = calculate_reliability("images/your_image.jpg")
```
Runs the model on 5 variants of the image (original, flip, brightness, darkness, rotation) and reports a HIGH / MEDIUM / LOW reliability score per defect based on how consistent the confidence is.

**Maintenance Priority Engine:**
```bash
python maintenance_priority/run_priority.py images/your_image.jpg [asset_id]   # one wheel, full report
python maintenance_priority/rank_fleet.py                                      # all wheels, ranked table
```
Combines defect type, severity, reliability, and (if an asset_id with history is given) the trend from the Digital Wheel Health Record into a single risk score, and recommends: Immediate inspection / Schedule maintenance / Monitor only.

## Running Tests

```bash
python -m tests.test_database
python -m tests.test_repository
python -m tests.test_history
python -m tests.test_dashboard
```

## Setup Notes

- `models/best.pt` (the trained YOLO weights) is not committed to git — place it manually at `models/best.pt` before running anything.
- `pip install -r requirements.txt` before first run (now includes `torch` and `grad-cam` for the explainability feature).

## License

Academic Final Year Project


## Latest Update

- Added Reliability Estimation module (Test-Time Augmentation).
- Added Explainable AI module (Grad-CAM / EigenCAM heatmaps with detection overlay).
- Added Maintenance Priority Engine (risk scoring + fleet ranking).
- Migrated Digital Wheel Health Record from JSON storage to SQLite.
- Added Repository Layer.
- Added Dashboard Statistics.
- Added Inspection History.
- Added Backend Test Suite.