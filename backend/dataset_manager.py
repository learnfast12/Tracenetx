import os
import uuid
from datetime import datetime
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploaded_datasets")
os.makedirs(UPLOAD_DIR, exist_ok=True)

DEFAULT_DATASET = os.path.join(BASE_DIR, "transactions.csv")

REQUIRED_COLUMNS = {"sender_id", "receiver_id", "amount", "timestamp"}
OPTIONAL_COLUMNS_DEFAULTS = {
    "sender_ip": "UNKNOWN",
    "sender_city": "UNKNOWN",
    "sender_phone": "UNKNOWN",
    "receiver_ip": "UNKNOWN",
    "transfer_type": "DIGITAL",
    "case_id": "DEFAULT",
}


class DatasetManager:
    def __init__(self):
        self._active_id = "demo"
        self._active_path = DEFAULT_DATASET
        self._registry = {
            "demo": {
                "id": "demo",
                "name": "Demo Network (transactions.csv)",
                "path": DEFAULT_DATASET,
                "uploaded_at": None,
                "rows": None,
            }
        }

    def validate_schema(self, df: pd.DataFrame):
        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(
                f"Missing required columns: {sorted(missing)}. "
                f"Required: {sorted(REQUIRED_COLUMNS)}"
            )

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        for col, default in OPTIONAL_COLUMNS_DEFAULTS.items():
            if col not in df.columns:
                df[col] = default
        return df

    def upload(self, filename: str, file_bytes: bytes) -> dict:
        dataset_id = uuid.uuid4().hex[:8]
        save_path = os.path.join(UPLOAD_DIR, f"{dataset_id}_{filename}")
        with open(save_path, "wb") as f:
            f.write(file_bytes)

        try:
            df = pd.read_csv(save_path)
        except Exception as e:
            os.remove(save_path)
            raise ValueError(f"Could not parse CSV: {e}")

        try:
            self.validate_schema(df)
        except ValueError:
            os.remove(save_path)
            raise

        df = self.normalize(df)
        df.to_csv(save_path, index=False)

        entry = {
            "id": dataset_id,
            "name": filename,
            "path": save_path,
            "uploaded_at": datetime.utcnow().isoformat(),
            "rows": len(df),
        }
        self._registry[dataset_id] = entry
        return entry

    def activate(self, dataset_id: str) -> dict:
        if dataset_id not in self._registry:
            raise KeyError(f"Unknown dataset_id: {dataset_id}")
        self._active_id = dataset_id
        self._active_path = self._registry[dataset_id]["path"]
        return self._registry[dataset_id]

    def get_active_path(self) -> str:
        return self._active_path

    def get_active_id(self) -> str:
        return self._active_id

    def list_datasets(self) -> list:
        return list(self._registry.values())


dataset_manager = DatasetManager()
