# Railway Wheel Health Assessment - Frontend Integration Guide

This document serves as the official frontend integration guide for the Railway Wheel Health Assessment backend. 

## 1. Project Overview

This is the backend API for the Railway Wheel Health Assessment system. It exposes a complete REST API that runs wheel images through an advanced AI pipeline:

**Pipeline:** Image Upload → YOLO Detection → Feature Extraction → Severity Assessment → TTA Reliability → Grad-CAM → Historical Trend → Maintenance Risk/Priority → Wheel Health Record.

The frontend is responsible for consuming this API to provide users with an intuitive dashboard for wheel inspections, historical tracking, and maintenance prioritization.

## 2. Backend Setup

### Environment and Dependencies
Ensure you have Python installed. The backend requires dependencies listed in `requirements.txt` (including FastAPI, Uvicorn, PyTorch, Ultralytics, OpenCV, Scikit-Learn, etc.).

### Starting the Backend
You can start the backend using either of the following commands:
```bash
# Standard Python execution
python main.py

# Or via uvicorn directly with hot-reload for development
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### URLs
- **Backend URL:** `http://localhost:8000`
- **Swagger UI (Interactive API Docs):** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

## 3. API Endpoints

### `GET /`
- **Purpose:** Quick health check.
- **Request:** None
- **Response:** `{"status": "ok", "message": "...", "docs": "/docs"}`

### `GET /api/health`
- **Purpose:** Detailed health check confirming that all AI models are loaded successfully.
- **Request:** None
- **Response:**
  ```json
  {
    "status": "ok",
    "models": {
      "yolo": true,
      "kmeans": true,
      "scaler": true,
      "mapping": true
    }
  }
  ```

### `POST /api/inspect`
- **Purpose:** Run a complete wheel inspection through the AI pipeline. (See Section 4 for detailed documentation).

### `GET /api/wheels`
- **Purpose:** Retrieve a list of all wheels in the system.
- **Request:** None
- **Response:** Array of WheelSummary objects.
- **Example Response:**
  ```json
  [
    {
      "asset_id": "WH000001",
      "wheel_identifier": null,
      "train_id": null,
      "coach_id": null,
      "status": "Monitor",
      "inspection_count": 2,
      "latest_inspection": "2026-10-03T13:17:24",
      "created_at": "2026-10-03 12:43:51",
      "last_updated": "2026-10-03 13:17:24"
    }
  ]
  ```

### `GET /api/wheels/{wheel_id}`
- **Purpose:** Retrieve detailed information about a specific wheel.
- **Request:** URL Path parameter `wheel_id` (the `asset_id`).
- **Response:** WheelDetail object.

### `GET /api/wheels/{wheel_id}/history`
- **Purpose:** Retrieve the inspection history timeline for a specific wheel.
- **Request:** URL Path parameter `wheel_id` (the `asset_id`).
- **Response:** Array of InspectionHistoryEntry objects ordered newest first. Each record represents a single detected defect instance.

### `GET /api/dashboard`
- **Purpose:** Retrieve fleet-wide statistics for the dashboard UI.
- **Request:** None
- **Response:** 
  ```json
  {
    "total_wheels": 1,
    "total_inspections": 2,
    "healthy": 0,
    "monitor": 1,
    "critical": 0,
    "severity_distribution": {"Mild": 1, "Severe": 1},
    "defect_distribution": {"Shelling": 1, "Cracks-Scratches": 1},
    "recent_inspections": [...]
  }
  ```

### `/outputs/annotated/{filename}` & `/outputs/gradcam/{filename}`
- **Purpose:** Static file serving for generated images. (See Section 8).
- **Method:** GET

## 4. Most Important: `/api/inspect`

This is the core endpoint of the application.

- **Method:** `POST`
- **URL:** `/api/inspect`
- **Content-Type:** `multipart/form-data`

### Request Fields
- `image` **(Required)**: The wheel image file (JPEG or PNG).
- `wheel_id` *(Optional)*: The asset ID of the wheel being inspected (e.g., `WH000001`). 
  - **Omit** this field if inspecting a brand new wheel. The backend will automatically generate a new `asset_id`.
  - **Supply** the existing `asset_id` when performing subsequent inspections on the same wheel to build historical tracking and trend analysis.
  - *Note: Do not use the Swagger default placeholder "string" as an actual wheel ID in production.*

### Response Structure & Fields
The endpoint returns a comprehensive JSON object describing the entire inspection result:

- `inspection_id`: Unique ID generated for this specific inspection event.
- `asset_id`: The internal system ID for the wheel (generated or echoed from `wheel_id`).
- `wheel_id`: The `wheel_id` provided in the request (if any).
- `image_name`: Original filename of the uploaded image.
- `inspection_date`: ISO 8601 timestamp of the inspection.
- `trend_status`: The aggregated historical trend of the wheel. Enum: `FIRST_INSPECTION`, `WORSENING`, `STABLE`, `IMPROVING`, `INSUFFICIENT_HISTORY`.
- `wheel_risk_score`: The overall risk score for the wheel (0-100), taken from its worst defect.
- `wheel_recommended_action`: The maintenance recommendation for the wheel (e.g., "Monitor only", "Schedule maintenance", "Immediate inspection").
- `total_defects_detected`: Number of individual defects found in the image.
- `defects`: Array of `DefectDetail` objects (See Section 5).
- `annotated_image_url`: Relative URL to the image with YOLO bounding boxes.
- `gradcam_image_url`: Relative URL to the Grad-CAM explainability heatmap.
- `processing_time_seconds`: Total time taken by the backend pipeline.

## 5. Defect Response

Inside the `defects` array, each object contains:

- `label`: Defect class name (e.g., "Shelling", "Cracks-Scratches").
- `confidence`: YOLO base detection confidence (0 to 1).
- `severity`: Clustered severity label (`Mild`, `Moderate`, `Severe`).
- `mean_confidence`: TTA (Test-Time Augmentation) averaged confidence across augmentations.
- `std_deviation`: Variance in TTA predictions (lower means more stable).
- `reliability`: Derived reliability category (`HIGH`, `MEDIUM`, `LOW`).
- `defect_weight`: Base risk weight assigned to this specific defect type.
- `severity_weight`: Risk weight assigned to the severity level.
- `trend_weight`: Risk weight assigned based on historical trend comparison.
- `reliability_factor`: Multiplier applied based on prediction reliability.
- `risk_score`: Final computed risk score (0-100) combining weights and reliability.
- `recommended_action`: Action recommended specifically for this defect instance.
- `trend_note`: Human-readable explanation of how this defect's trend was calculated against history.
- `features`: Object containing extracted numerical features:
  - `features.area`: Defect area in pixels.
  - `features.perimeter`: Defect perimeter in pixels.
  - `features.aspect_ratio`: Width/Height ratio of the bounding rect.
  - `features.edge_density`: Edge pixel density within the defect mask.
  - `features.entropy`: Shannon entropy of the defect mask.

### Distinctions in Metrics
- **YOLO `confidence`**: How sure the base model is that the bounding box contains the defect.
- **TTA `mean_confidence` & `std_deviation`**: Metrics generated by running the image through the model multiple times with variations (flips, brightness). Helps detect flaky predictions.
- **`reliability`**: Categorical assessment (HIGH/MEDIUM/LOW) derived directly from the TTA standard deviation.
- **`severity`**: Data-driven physical severity (Mild/Moderate/Severe) determined by K-Means clustering of the extracted geometric `features`.
- **`risk_score`**: The ultimate business-logic score that aggregates defect type, physical severity, historical trend, and AI reliability to prioritize maintenance.

## 6. Trend/History Logic

The backend tracks how a wheel's health changes over time. **Crucially, trends are calculated strictly per defect type.**

- Shelling history is only ever compared against previous Shelling records on that wheel.
- Cracks-Scratches history is only ever compared against previous Cracks-Scratches records on that wheel.

**Defect Trend Statuses:**
- `FIRST_INSPECTION`: No prior history exists for this wheel, or this specific defect type has never been seen on this wheel before.
- `INSUFFICIENT_HISTORY`: Not enough historical records to form a trend.
- `WORSENING`: The current severity rank is higher than the historical average for this defect.
- `STABLE`: The current severity rank equals the historical average.
- `IMPROVING`: The current severity rank is lower than the historical average.

**Wheel-Level Aggregation:**
The wheel-level `trend_status` is derived from individual defect trends using a safety-first aggregation rule:
1. If ANY defect is `WORSENING`, the wheel trend is `WORSENING`.
2. Else, if ANY defect is `STABLE`, the wheel trend is `STABLE`.
3. Else, if ALL evaluated defects are `IMPROVING`, the wheel trend is `IMPROVING`.

*Note: For the trend system to work, the frontend MUST supply the same `wheel_id` in `/api/inspect` for subsequent inspections of the same physical wheel.*

## 7. Wheel Lifecycle

- **`asset_id`**: The primary internal database key for a wheel (e.g., `WH000001`). Generated by the backend if not provided during the first inspection.
- **`wheel_id`**: Often synonymous with `asset_id` in the API requests. It's the ID the user/frontend provides to track a specific wheel.
- **`wheel_identifier`**: An optional secondary field in the database for external/manufacturing serial numbers.
- **Inspection Records**: When an image is inspected, the backend extracts all defects. **Each detected defect instance is saved as a separate row in the inspection history database**, tied to the same `asset_id` and `inspection_date`. Thus, one image upload can yield multiple history records.

## 8. Image URLs

The API returns `annotated_image_url` and `gradcam_image_url` as relative paths.

**Example API Response:**
`"annotated_image_url": "/outputs/annotated/frame2304.jpg"`

**Frontend Responsibility:**
The frontend must prepend the backend base URL to display these images.
```javascript
const backendUrl = "http://localhost:8000";
const imageUrl = backendUrl + inspectionResult.annotated_image_url;
// Result: "http://localhost:8000/outputs/annotated/frame2304.jpg"
```

## 9. Frontend Integration Flow

**Recommended Flow:**
1. **User Action:** User selects a wheel image and (optionally) inputs an existing Wheel ID.
2. **API Call:** Frontend sends a `multipart/form-data` POST request to `/api/inspect`.
3. **Processing:** Frontend displays a loading state (pipeline takes ~1-3 seconds).
4. **Results:** Backend returns the `InspectionResponse` JSON.
5. **UI Display:**
   - Show the annotated and Grad-CAM images (prepending the base URL).
   - Display the overall wheel risk score, action, and trend.
   - List out the `defects` array in cards or a table, showing `severity`, `reliability`, and `risk_score` for each.
6. **Navigation:** Frontend allows the user to view historical timelines by fetching `/api/wheels/{wheel_id}/history`.
7. **Dashboard:** The main landing page fetches `/api/dashboard` to show fleet-wide health stats.

## 10. Frontend UI Mapping

Suggested mapping of API fields to UI components:

| API Field | Suggested Frontend Display |
| :--- | :--- |
| `label` | Defect Name / Card Title |
| `confidence` | Base AI Confidence Bar/Text |
| `severity` | Severity Badge (e.g., Green/Yellow/Red) |
| `reliability` | Shield/Checkmark icon (High/Med/Low) |
| `risk_score` | Prominent Risk Score gauge (0-100) |
| `recommended_action` | Primary Call-to-Action button or alert banner |
| `trend_status` | Up/Down/Flat trend arrow indicator |
| `trend_note` | Tooltip or subtext explaining the trend |
| `annotated_image_url` | Primary Detection Image Viewer |
| `gradcam_image_url` | Secondary "AI Explainability" Heatmap overlay |

## 11. CORS Configuration

The backend is currently configured with permissive CORS settings to facilitate seamless local development with a separate frontend server.

```python
allow_origins=["*"]
```
This allows your frontend (e.g., running on `http://localhost:3000` or `http://localhost:5173`) to communicate directly with the backend at `http://localhost:8000` without encountering CORS blocks.

## 12. Important Current Limitations

Please be aware of the following actual implementations limits when designing the UI:

- **Grad-CAM is not segmentation:** The Grad-CAM image is a generalized class-activation heatmap showing where the model "looked." It is not a pixel-perfect semantic segmentation mask. Do not describe it to users as a precise boundary.
- **Processing Time:** The Test-Time Augmentation (TTA) reliability step requires running inference multiple times. This increases processing time per upload compared to standard YOLO. Ensure the UI has adequate loading indicators.
- **Database:** The backend currently uses a local SQLite database (`railway.db`). 
- **Authentication:** There is currently no authentication or authorization mechanism implemented.
- **Static Files:** Annotated and Grad-CAM images are saved locally to the `outputs/` directory and served statically.

## 13. API Contract Stability

**Notice for Frontend Developers:**
Please consume the exact documented response fields (like `risk_score`, `severity`, `trend_status`) rather than attempting to manually calculate or hard-code logic based on raw `features` or `confidence` values. 

The internal ML implementations (such as the K-Means severity clustering models, risk weighting formulas, or underlying YOLO versions) may be retrained or improved in the future without changing the API contract structure. Relying on the high-level assessment fields ensures the frontend won't break during backend upgrades.