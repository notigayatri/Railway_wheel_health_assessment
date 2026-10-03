import json
from pathlib import Path
import joblib
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# Load extracted features - prefer full training dataset
csv_path = Path("outputs/training_features.csv")
if not csv_path.exists():
    csv_path = Path("outputs/features.csv")

if not csv_path.exists():
    raise FileNotFoundError(f"Feature file not found: {csv_path}")

df = pd.read_csv(csv_path)

# Check if dataframe is empty
if df.empty:
    raise ValueError(f"{csv_path} is empty. Run feature extraction first.")

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

# Fixed 3 clusters corresponding to Mild, Moderate, Severe
n_clusters = 3
print(f"Training K-Means with {n_clusters} clusters on {len(df)} samples from {csv_path}...")

kmeans = KMeans(
    n_clusters=n_clusters,
    random_state=42,
    n_init=10
)

# Train clustering model
df["cluster"] = kmeans.fit_predict(X_scaled)

# Inspect cluster centers in unscaled units to establish documented severity mapping
centers_unscaled = scaler.inverse_transform(kmeans.cluster_centers_)
centers_df = pd.DataFrame(centers_unscaled, columns=feature_columns)
centers_df["cluster"] = range(n_clusters)
print("\nUnscaled Cluster Centers:")
print(centers_df[["cluster", "area", "perimeter", "aspect_ratio", "edge_density", "entropy"]])

# Severity mapping established from physical defect distributions:
# - Cluster with lowest area and perimeter represents minor surface flaws -> Mild
# - Cluster with intermediate area and high aspect ratio represents elongated cracks -> Moderate
# - Cluster with highest area, perimeter, and entropy represents extensive surface shelling/spalling -> Severe
area_means = df.groupby("cluster")["area"].mean().sort_values()
mild_cluster = int(area_means.index[0])
mod_cluster = int(area_means.index[1])
sev_cluster = int(area_means.index[2])

severity_map = {
    mild_cluster: "Mild",
    mod_cluster: "Moderate",
    sev_cluster: "Severe"
}

print(f"\nDocumented Cluster to Severity Mapping: {severity_map}")

df["severity"] = df["cluster"].map(severity_map)

# Display sample results
print("\nSeverity Distribution:")
print(df["severity"].value_counts())

# Save trained models and mapping
save_dir = Path("severity")
save_dir.mkdir(exist_ok=True)

kmeans_path = save_dir / "kmeans_model.pkl"
scaler_path = save_dir / "scaler.pkl"
mapping_path = save_dir / "severity_mapping.json"

joblib.dump(kmeans, kmeans_path)
joblib.dump(scaler, scaler_path)

with open(mapping_path, "w") as f:
    json.dump({str(k): v for k, v in severity_map.items()}, f, indent=4)

print(f"\nSaved K-Means model: {kmeans_path}")
print(f"Saved scaler: {scaler_path}")
print(f"Saved severity mapping: {mapping_path}")

print("\nSeverity clustering completed successfully!")