import io
from typing import List

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

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
    name: str = Field(min_length=2, max_length=255)
    sensitive_attributes: List[str] = Field(default_factory=list)


@router.post("/api/upload/dataset")
async def upload_dataset(file: UploadFile = File(...)):
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

    return {
        "filename": file.filename,
        "row_count": int(len(dataframe)),
        "columns": columns,
        "suggested_sensitive_attributes": suggested,
    }


@router.post("/api/models/register")
def register_model(payload: ModelRegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(ModelRegistry).filter(ModelRegistry.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Model name already exists.")

    sensitive_attributes = sorted(
        {
            attribute.strip()
            for attribute in payload.sensitive_attributes
            if isinstance(attribute, str) and attribute.strip()
        }
    )

    model = ModelRegistry(
        name=payload.name.strip(),
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
