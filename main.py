import sys
from pathlib import Path
import subprocess

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from severity.predict_severity import process_image

IMAGE_PATH = PROJECT_ROOT / "images" / "frame2304_jpg.rf.0188ac25e86fafbbdc3ca9a47b63a8e5.jpg"

# Step 1: Detect + extract features
process_image(IMAGE_PATH)

# Step 2: Train/apply clustering
subprocess.run([sys.executable, str(PROJECT_ROOT / "severity" / "cluster_train.py")])

print("Pipeline completed successfully.")