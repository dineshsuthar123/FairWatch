from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    sensitive_attributes = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    predictions = relationship("Prediction", back_populates="model", cascade="all, delete-orphan")
    bias_reports = relationship("BiasReport", back_populates="model", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="model", cascade="all, delete-orphan")


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("model_registry.id"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    input_features = Column(JSON, nullable=False, default=dict)
    output_decision = Column(Integer, nullable=False)
    group_label = Column(String(255), nullable=False, index=True)

    model = relationship("ModelRegistry", back_populates="predictions")


class BiasReport(Base):
    __tablename__ = "bias_reports"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("model_registry.id"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    metric_name = Column(String(255), nullable=False, index=True)
    group_a = Column(String(255), nullable=False)
    group_b = Column(String(255), nullable=False)
    disparity_score = Column(Float, nullable=False)
    severity = Column(String(20), nullable=False, index=True)
    explanation = Column(Text, nullable=False, default="")
    feature_contributions = Column(JSON, nullable=False, default=dict)
    metric_meaning = Column(String(512), nullable=False, default="")
    fix_suggestions = Column(JSON, nullable=False, default=dict)
    monitoring_type = Column(String(64), nullable=False, default="batch_window_100")

    model = relationship("ModelRegistry", back_populates="bias_reports")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("model_registry.id"), nullable=False, index=True)
    triggered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    message = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False, index=True)
    resolved = Column(Boolean, nullable=False, default=False, index=True)

    model = relationship("ModelRegistry", back_populates="alerts")
