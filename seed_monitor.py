import argparse
import json
import random
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


DEFAULT_DATASET = Path(__file__).resolve().parent / "datasets" / "adult.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--model-id", type=int, default=None)
    parser.add_argument("--model-name", default="AdultIncomeLogReg")
    parser.add_argument("--records", type=int, default=250)
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--delay", type=float, default=0.02)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--inject-bias", action="store_true")
    parser.add_argument("--female-reject-rate", type=float, default=0.65)
    return parser.parse_args()


def http_json(method: str, url: str, payload: Optional[Dict[str, Any]] = None, timeout: int = 60) -> Dict[str, Any]:
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

    if not raw.strip():
        return {}
    return json.loads(raw)


def ensure_model(base_url: str, model_name: str, model_id: Optional[int]) -> int:
    if model_id is not None:
        return model_id

    models_response = http_json("GET", f"{base_url}/api/models")
    for model in models_response.get("models", []):
        if str(model.get("name")) == model_name:
            return int(model["id"])

    created = http_json(
        "POST",
        f"{base_url}/api/models/register",
        {
            "name": model_name,
            "sensitive_attributes": ["gender", "race"],
        },
    )
    return int(created["id"])


def load_and_prepare_dataset(dataset_path: Path):
    dataframe = pd.read_csv(dataset_path)

    object_columns = dataframe.select_dtypes(include=["object"]).columns.tolist()
    for column in object_columns:
        dataframe[column] = dataframe[column].astype(str).str.strip()

    if "income" not in dataframe.columns:
        raise RuntimeError("income column not found in dataset")
    if "gender" not in dataframe.columns or "race" not in dataframe.columns:
        raise RuntimeError("gender and race columns are required in dataset")

    labels = (dataframe["income"].astype(str).str.strip() == ">50K").astype(int)
    raw_features = dataframe.drop(columns=["income"]).copy()
    categorical_columns = raw_features.select_dtypes(include=["object"]).columns.tolist()
    encoded_features = pd.get_dummies(raw_features, columns=categorical_columns, dtype=int)

    return raw_features, encoded_features, labels


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


def normalize_record_count(requested: int, available: int) -> int:
    capped = max(200, min(int(requested), 500))
    capped = min(capped, available)
    if capped >= 25:
        capped -= capped % 25
        if capped == 0:
            capped = min(25, available)
    return capped


def main() -> None:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    dataset_path = Path(args.dataset).resolve()
    if not dataset_path.exists():
        raise FileNotFoundError(dataset_path)

    model_id = ensure_model(base_url, args.model_name, args.model_id)

    raw_features, encoded_features, labels = load_and_prepare_dataset(dataset_path)
    raw_train, raw_test, x_train, x_test, y_train, y_test = train_test_split(
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

    test_frame = raw_test.reset_index(drop=True)
    test_labels = y_test.reset_index(drop=True)
    prediction_series = pd.Series(predictions).reset_index(drop=True)

    total_records = normalize_record_count(args.records, len(test_frame))
    randomizer = random.Random(args.random_state)

    for index in range(total_records):
        row = test_frame.iloc[index]
        prediction = int(prediction_series.iloc[index])
        label = int(test_labels.iloc[index])

        gender_value = str(row["gender"]).strip()
        race_value = str(row["race"]).strip()

        if (
            args.inject_bias
            and gender_value.lower() == "female"
            and prediction == 1
            and randomizer.random() < args.female_reject_rate
        ):
            prediction = 0

        payload = {
            "prediction": prediction,
            "label": label,
            "features": {key: to_builtin(value) for key, value in row.to_dict().items()},
            "sensitive": {
                "gender": 1 if gender_value.lower() == "male" else 0,
                "race": 1 if race_value.lower() == "white" else 0,
            },
        }

        query = urllib.parse.urlencode({"model_id": model_id})
        endpoint = f"{base_url}/monitor?{query}"

        try:
            response = http_json("POST", endpoint, payload, timeout=120)
        except Exception as exc:
            print(f"[{index + 1}/{total_records}] /monitor failed: {exc}")
            time.sleep(args.delay)
            continue

        if response.get("analysis_triggered"):
            print(
                f"[{index + 1}/{total_records}] analysis triggered | "
                f"reports={response.get('saved_reports', 0)} | "
                f"summary={response.get('analysis_summary', {})}"
            )
        elif (index + 1) % 25 == 0:
            print(f"[{index + 1}/{total_records}] streamed")

        time.sleep(args.delay)

    print(
        json.dumps(
            {
                "model_id": model_id,
                "records_sent": total_records,
                "inject_bias": bool(args.inject_bias),
            }
        )
    )


if __name__ == "__main__":
    main()
