import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import joblib
from pathlib import Path

# Load extracted features
csv_path = Path("outputs/features.csv")

if not csv_path.exists():
    raise FileNotFoundError(f"Feature file not found: {csv_path}")

df = pd.read_csv(csv_path)

# Check if dataframe is empty
if df.empty:
    raise ValueError("features.csv is empty. Run feature extraction first.")

# Select features for clustering
feature_columns = [
    "area",
    "perimeter",
    "aspect_ratio",
    "edge_density",
    "entropy"
]

X = df[feature_columns]

# Normalize features
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Choose number of clusters dynamically
n_clusters = min(3, len(df))

print(f"Training K-Means with {n_clusters} cluster(s)")

kmeans = KMeans(
    n_clusters=n_clusters,
    random_state=42,
    n_init="auto"
)

# Train clustering model
df["cluster"] = kmeans.fit_predict(X_scaled)

# Map clusters to severity labels
if n_clusters == 3:
    severity_map = {
        0: "Mild",
        1: "Moderate",
        2: "Severe"
    }

elif n_clusters == 2:
    severity_map = {
        0: "Moderate",
        1: "Severe"
    }

else:
    severity_map = {
        0: "Moderate"
    }

df["severity"] = df["cluster"].map(severity_map)

# Display results
print("\\nSeverity Results:")
print(df[["class", "area", "cluster", "severity"]])

# Save trained models
Path("severity").mkdir(exist_ok=True)

joblib.dump(kmeans, "severity/kmeans_model.pkl")
joblib.dump(scaler, "severity/scaler.pkl")

# Save updated CSV
df.to_csv(csv_path, index=False)

print("\\nSaved updated feature file:", csv_path)
print("Saved K-Means model: severity/kmeans_model.pkl")
print("Saved scaler: severity/scaler.pkl")

print("\\nSeverity clustering completed successfully!")