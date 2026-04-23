import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

DATASET_PATH = Path(__file__).resolve().parents[1] / "datasets" / "adult.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--records", type=int, default=200)
    parser.add_argument("--delay", type=float, default=0.01)
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--inject-bias", action="store_true")
    parser.add_argument("--female-reject-rate", type=float, default=0.6)
    return parser.parse_args()


def http_json(method: str, url: str, payload: Optional[Dict[str, Any]] = None, timeout: int = 120) -> Dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url=url, data=body, headers=headers, method=method.upper())

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{exc.code} {exc.reason}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Connection failed: {exc.reason}") from exc

    return json.loads(raw) if raw.strip() else {}


def ensure_model(base_url: str) -> int:
    model_name = f"AdultMonitor-{int(time.time())}"
    response = http_json(
        "POST",
        f"{base_url}/api/models/register",
        {
            "name": model_name,
            "sensitive_attributes": ["gender", "race"],
        },
    )
    return int(response["id"])


def to_builtin(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def load_dataset():
    dataframe = pd.read_csv(DATASET_PATH)
    object_columns = dataframe.select_dtypes(include=["object"]).columns.tolist()
    for column in object_columns:
        dataframe[column] = dataframe[column].astype(str).str.strip()

    labels = (dataframe["income"] == ">50K").astype(int)
    raw_features = dataframe.drop(columns=["income"]).copy()
    categorical_columns = raw_features.select_dtypes(include=["object"]).columns.tolist()
    encoded_features = pd.get_dummies(raw_features, columns=categorical_columns, dtype=int)
    return raw_features, encoded_features, labels


def main() -> None:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    model_id = ensure_model(base_url)

    raw_features, encoded_features, labels = load_dataset()
    _, raw_test, x_train, x_test, y_train, y_test = train_test_split(
        raw_features,
        encoded_features,
        labels,
        test_size=args.test_size,
        random_state=args.random_state,
        stratify=labels,
    )

    model = LogisticRegression(max_iter=2000, solver="liblinear")
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)

    raw_test = raw_test.reset_index(drop=True)
    y_test = y_test.reset_index(drop=True)
    predictions = pd.Series(predictions).reset_index(drop=True)

    total_records = min(max(20, args.records), len(raw_test))

    for index in range(total_records):
        row = raw_test.iloc[index]
        prediction = int(predictions.iloc[index])
        label = int(y_test.iloc[index])

        gender_value = str(row["gender"]).strip().lower()
        race_value = str(row["race"]).strip().lower()

        if (
            args.inject_bias
            and gender_value == "female"
            and prediction == 1
            and np.random.random() < args.female_reject_rate
        ):
            prediction = 0

        payload = {
            "prediction": prediction,
            "label": label,
            "features": {key: to_builtin(value) for key, value in row.to_dict().items()},
            "sensitive": {
                "gender": 1 if gender_value == "male" else 0,
                "race": 1 if race_value == "white" else 0,
            },
        }

        query = urllib.parse.urlencode({"model_id": model_id})
        endpoint = f"{base_url}/monitor?{query}"

        try:
            response = http_json("POST", endpoint, payload)
            print(f"[TEST] monitor {index + 1}/{total_records}: {response}")
        except Exception as exc:
            print(f"[TEST] /monitor failed for record {index + 1}: {exc}")

        time.sleep(args.delay)

    latest = http_json("GET", f"{base_url}/api/reports/{model_id}/latest")
    print("[TEST] latest report:", latest)

    regenerated = http_json("POST", f"{base_url}/api/reports/{model_id}/latest/regenerate")
    print("[TEST] regenerated report:", regenerated)


if __name__ == "__main__":
    main()
