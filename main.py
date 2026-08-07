import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Reliability module
from reliability.reliability import calculate_reliability

# Detection + feature extraction + severity prediction
from severity.predict_severity import predict_image


def main(image_path):
    print(f"\\nProcessing image: {image_path.name}")

    # Step 1: YOLO detection + feature extraction
    # predict_image should internally load kmeans_model.pkl
    severity_results = predict_image(image_path)

    # Step 2: Reliability analysis
    reliability_results = calculate_reliability(image_path)

    # Step 3: Final combined output
    print("\\n===== FINAL HEALTH ASSESSMENT =====")

    for defect, info in reliability_results.items():
        severity = severity_results.get(defect, "Unknown")

        print(f"\\nDefect: {defect}")
        print(f"  Severity        : {severity}")
        print(f"  Mean Confidence : {info['mean_confidence']}")
        print(f"  Std Deviation   : {info['std_deviation']}")
        print(f"  Reliability     : {info['reliability']}")

    print("\\nPipeline completed successfully.")


if __name__ == "__main__":
    IMAGE_PATH = (
        PROJECT_ROOT
        / "dataset"
        / "test"
        / "images"
        / "frame2304_jpg.rf.0188ac25e86fafbbdc3ca9a47b63a8e5.jpg"
    )

    main(IMAGE_PATH)