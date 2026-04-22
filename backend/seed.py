import json
import random
from collections import Counter
from datetime import datetime, timedelta
from typing import List, Tuple

from agents.bias_detector import run_bias_analysis
from agents.drift_agent import detect_drift
from database import SessionLocal, init_db
from models import Alert, BiasReport, ModelRegistry, Prediction

MODEL_NAME = "LoanApprovalModel"
SENSITIVE_ATTRIBUTES = ["gender", "race"]
TOTAL_PREDICTIONS = 200


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def approval_probability(gender: str, race: str, day_bucket: int) -> float:
    gender_rate = 0.75 if gender == "male" else 0.45
    race_rate = 0.80 if race == "white" else 0.52

    base_rate = (gender_rate + race_rate) / 2.0

    # Build in mild drift: privileged groups become slightly more favored over time.
    drift_factor = day_bucket / 29.0
    if gender == "male":
        base_rate += 0.08 * drift_factor
    else:
        base_rate -= 0.08 * drift_factor

    if race == "white":
        base_rate += 0.06 * drift_factor
    else:
        base_rate -= 0.06 * drift_factor

    noise = random.uniform(-0.04, 0.04)
    return clamp(base_rate + noise, 0.03, 0.97)


def true_label_probability(gender: str, race: str) -> float:
    base = 0.62
    if gender == "female":
        base -= 0.02
    if race == "black":
        base -= 0.03
    return clamp(base + random.uniform(-0.05, 0.05), 0.05, 0.95)


def reset_existing_seed_model(db) -> None:
    existing = db.query(ModelRegistry).filter(ModelRegistry.name == MODEL_NAME).first()
    if existing is None:
        return

    db.query(Alert).filter(Alert.model_id == existing.id).delete(synchronize_session=False)
    db.query(BiasReport).filter(BiasReport.model_id == existing.id).delete(synchronize_session=False)
    db.query(Prediction).filter(Prediction.model_id == existing.id).delete(synchronize_session=False)
    db.query(ModelRegistry).filter(ModelRegistry.id == existing.id).delete(synchronize_session=False)
    db.commit()


def seed_predictions(db, model_id: int) -> List[Prediction]:
    now = datetime.utcnow()
    rows: List[Prediction] = []

    for index in range(TOTAL_PREDICTIONS):
        day_bucket = index % 30
        gender = random.choice(["male", "female"])
        race = random.choice(["white", "black"])

        decision_probability = approval_probability(gender, race, day_bucket)
        output_decision = 1 if random.random() < decision_probability else 0

        truth_probability = true_label_probability(gender, race)
        true_label = 1 if random.random() < truth_probability else 0

        timestamp = now - timedelta(
            days=(29 - day_bucket),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59),
        )

        input_features = {
            "credit_score": random.randint(520, 840),
            "income": random.randint(24000, 190000),
            "debt_to_income": round(random.uniform(0.05, 0.65), 2),
            "true_label": true_label,
        }

        group_label = json.dumps({"gender": gender, "race": race}, sort_keys=True)

        rows.append(
            Prediction(
                model_id=model_id,
                timestamp=timestamp,
                input_features=input_features,
                output_decision=output_decision,
                group_label=group_label,
            )
        )

    db.add_all(rows)
    db.commit()
    return rows


def seed_historical_reports(db, model_id: int) -> int:
    now = datetime.utcnow()
    inserted = 0

    for day_offset in range(30):
        as_of = now - timedelta(days=(29 - day_offset))
        analysis = run_bias_analysis(model_id=model_id, window_size=100, db=db, as_of=as_of)

        for item in analysis.get("reports", []):
            db.add(
                BiasReport(
                    model_id=model_id,
                    timestamp=as_of,
                    metric_name=item["metric_name"],
                    group_a=item["group_a"],
                    group_b=item["group_b"],
                    disparity_score=float(item["disparity_score"]),
                    severity=item["severity"],
                    explanation="Seeded baseline fairness report from synthetic monitoring data.",
                )
            )
            inserted += 1

    db.commit()
    return inserted


def approval_rate_by_group(predictions: List[Prediction]) -> Tuple[float, float, float, float]:
    gender_total = Counter()
    gender_approved = Counter()
    race_total = Counter()
    race_approved = Counter()

    for prediction in predictions:
        group = json.loads(prediction.group_label)
        gender = group.get("gender", "unknown")
        race = group.get("race", "unknown")

        gender_total[gender] += 1
        race_total[race] += 1

        if prediction.output_decision == 1:
            gender_approved[gender] += 1
            race_approved[race] += 1

    male_rate = gender_approved["male"] / gender_total["male"] if gender_total["male"] else 0.0
    female_rate = gender_approved["female"] / gender_total["female"] if gender_total["female"] else 0.0
    white_rate = race_approved["white"] / race_total["white"] if race_total["white"] else 0.0
    black_rate = race_approved["black"] / race_total["black"] if race_total["black"] else 0.0

    return male_rate, female_rate, white_rate, black_rate


def main() -> None:
    random.seed(42)
    init_db()

    db = SessionLocal()
    try:
        reset_existing_seed_model(db)

        model = ModelRegistry(name=MODEL_NAME, sensitive_attributes=SENSITIVE_ATTRIBUTES)
        db.add(model)
        db.commit()
        db.refresh(model)

        predictions = seed_predictions(db, model.id)
        report_count = seed_historical_reports(db, model.id)
        drift = detect_drift(model.id, db=db)

        male_rate, female_rate, white_rate, black_rate = approval_rate_by_group(predictions)

        print("FairWatch seed complete.")
        print(f"Model ID: {model.id}")
        print(f"Predictions inserted: {len(predictions)}")
        print(f"Bias reports inserted: {report_count}")
        print(f"Male approval rate: {male_rate:.2%}")
        print(f"Female approval rate: {female_rate:.2%}")
        print(f"White approval rate: {white_rate:.2%}")
        print(f"Black approval rate: {black_rate:.2%}")
        print(f"Drift detection result: {drift}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
