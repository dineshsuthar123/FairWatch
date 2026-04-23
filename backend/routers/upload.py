import io
import time
import requests
from typing import Any, List, Optional

import pandas as pd
from fastapi import Body, BackgroundTasks
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split

from database import get_db
from models import ModelRegistry

router = APIRouter(tags=["upload"])

SENSITIVE_KEYWORDS = {
    "gender",
    "sex",
    "race",
    "age",
    "religion",
    "ethnicity",
}

class ModelRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: Optional[str] = Field(default=None)
    model_name: Optional[str] = Field(default=None)
    sensitive_attributes: List[Any] = Field(default_factory=list)
    sensitiveAttributes: List[Any] = Field(default_factory=list)


def auto_feed_predictions(df: pd.DataFrame):
    print("Auto-feeding predictions started")
    time.sleep(5)
    try:
        target_col = None
        for col in df.columns:
            if col.lower() in ['income', 'target', 'label', 'decision', 'approved']:
                target_col = col
                break
        if not target_col:
            target_col = df.columns[-1]

        df = df.dropna()
        y = df[target_col]
        X = df.drop(columns=[target_col])

        for col in X.columns:
            if X[col].dtype == 'object' or str(X[col].dtype) == 'category':
                X[col] = LabelEncoder().fit_transform(X[col].astype(str))

        if y.dtype == 'object' or str(y.dtype) == 'category' or not str(y.dtype).startswith(('int', 'float')):
            y = LabelEncoder().fit_transform(y.astype(str))

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        model = LogisticRegression(max_iter=1000)
        model.fit(X_train, y_train)

        preds = model.predict(X_test)
        num_preds = min(200, len(preds))
        url = "http://localhost:8000/monitor"
        y_test_array = getattr(y_test, "values", y_test)

        for i in range(num_preds):
            row = X_test.iloc[i]
            label = int(y_test_array[i])
            pred = int(preds[i])

            features_dict = row.to_dict()
            sensitive_dict = {}
            for k in list(features_dict.keys()):
                if k.lower() in SENSITIVE_KEYWORDS:
                    sensitive_dict[k] = features_dict[k]

            payload = {
                "prediction": pred,
                "label": label,
                "features": features_dict,
                "sensitive": sensitive_dict
            }
            try:
                requests.post(url, json=payload, timeout=5)
            except Exception as e:
                pass
                
    except Exception as e:
        print(f"Error in auto_feed_predictions: {e}")


@router.post("/api/upload/dataset")
async def upload_dataset(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a valid CSV file.")

    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        dataframe = pd.read_csv(io.BytesIO(payload))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV file: {exc}") from exc

    columns = [str(column) for column in dataframe.columns.tolist()]
    suggested = [
        column
        for column in columns
        if any(keyword in column.lower() for keyword in SENSITIVE_KEYWORDS)
    ]
    
    background_tasks.add_task(auto_feed_predictions, dataframe.copy())

    return {
        "filename": file.filename,
        "row_count": int(len(dataframe)),
        "columns": columns,
        "suggested_sensitive_attributes": suggested,
    }


@router.post("/api/models/register")
def register_model(payload: ModelRegisterRequest = Body(...), db: Session = Depends(get_db)):
    raw_name = str(payload.name or payload.model_name or "").strip()
    if len(raw_name) < 2:
        raise HTTPException(status_code=400, detail="Model name must be at least 2 characters.")

    existing = db.query(ModelRegistry).filter(ModelRegistry.name == raw_name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Model name already exists.")

    raw_attributes = list(payload.sensitive_attributes or payload.sensitiveAttributes or [])
    sensitive_attributes = sorted(
        {
            str(attribute).strip()
            for attribute in raw_attributes
            if str(attribute).strip()
        }
    )

    model = ModelRegistry(
        name=raw_name,
        sensitive_attributes=sensitive_attributes,
    )

    db.add(model)
    db.commit()
    db.refresh(model)

    return {
        "id": model.id,
        "name": model.name,
        "sensitive_attributes": model.sensitive_attributes,
        "created_at": model.created_at,
    }


@router.get("/api/models")
def list_models(db: Session = Depends(get_db)):
    models = db.query(ModelRegistry).order_by(ModelRegistry.created_at.desc()).all()
    return {
        "models": [
            {
                "id": model.id,
                "name": model.name,
                "sensitive_attributes": model.sensitive_attributes,
                "created_at": model.created_at,
            }
            for model in models
        ]
    }
