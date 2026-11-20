import os
import pickle
import numpy as np
from typing import Dict, Any, Optional

class MovementQualityClassifier:
    """
    Modular Machine Learning interface for rehabilitation movement-quality assessment.
    Designed for future deployment of trained scikit-learn or XGBoost models.
    """
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.model = None
        self.scaler = None
        self.is_loaded = False
        self.candidate_classes = ["Normal movement", "Restricted movement", "Irregular movement"]
        self.model_identifier = "None"
        self.version = "unconfigured"

        if model_path and os.path.exists(model_path):
            self._load_model(model_path)

    def _load_model(self, path: str):
        try:
            with open(path, "rb") as f:
                checkpoint = pickle.load(f)
                self.model = checkpoint.get("model")
                self.scaler = checkpoint.get("scaler")
                self.model_identifier = checkpoint.get("name", "RandomForestClassifier")
                self.version = checkpoint.get("version", "v1.0")
                self.is_loaded = True
        except Exception:
            self.is_loaded = False

    def extract_features(
        self,
        rom: float,
        repetitions: int,
        avg_rep_duration: float,
        rep_duration_variation: float,
        peak_angle_variation: float,
        smoothness_score: float,
        avg_angular_velocity: float = 0.0
    ) -> np.ndarray:
        """
        Standardizes feature extraction vector from biomechanical kinematics:
        [rom, repetitions, avg_duration, duration_variance, peak_angle_variance, smoothness, angular_velocity]
        """
        features = np.array([
            rom,
            float(repetitions),
            avg_rep_duration,
            rep_duration_variation,
            peak_angle_variation,
            smoothness_score,
            avg_angular_velocity
        ], dtype=np.float32).reshape(1, -1)
        return features

    def predict(self, feature_vector: np.ndarray) -> Dict[str, Any]:
        """
        Performs inference if a verified trained model is loaded.
        Otherwise cleanly reports that ML model is unconfigured, avoiding false claims.
        """
        if not self.is_loaded or self.model is None:
            return {
                "inference_status": "NOT_CONFIGURED",
                "message": "ML movement assessment is not configured yet.",
                "predicted_class": None,
                "confidence": None,
                "model_identifier": "None",
                "version": "unconfigured",
                "clinical_validation": "None - academic research model interface"
            }

        try:
            feats = feature_vector
            if self.scaler:
                feats = self.scaler.transform(feats)
                
            pred_idx = self.model.predict(feats)[0]
            pred_class = self.candidate_classes[int(pred_idx)] if int(pred_idx) < len(self.candidate_classes) else str(pred_idx)
            
            confidence = None
            if hasattr(self.model, "predict_proba"):
                probs = self.model.predict_proba(feats)[0]
                confidence = float(np.max(probs))

            return {
                "inference_status": "SUCCESS",
                "message": "Model inference completed.",
                "predicted_class": pred_class,
                "confidence": round(confidence, 3) if confidence else None,
                "model_identifier": self.model_identifier,
                "version": self.version,
                "clinical_validation": "Candidate prototype - unvalidated"
            }
        except Exception as e:
            return {
                "inference_status": "ERROR",
                "message": f"Inference execution failed: {str(e)}",
                "predicted_class": None,
                "confidence": None,
                "model_identifier": self.model_identifier,
                "version": self.version,
                "clinical_validation": "None"
            }

    @staticmethod
    def calculate_demonstration_heuristic(
        rom: float,
        target_angle: float,
        rep_duration_variation: float,
        smoothness_score: float
    ) -> Dict[str, Any]:
        """
        Clearly labelled rule-based demonstration calculation.
        Explicitly disclaimed as NOT an ML prediction or clinical diagnosis.
        """
        rom_ratio = min(1.0, rom / max(target_angle, 1.0))
        consistency_ratio = smoothness_score / 100.0
        heuristic_score = round((rom_ratio * 0.6 + consistency_ratio * 0.4) * 100.0, 1)

        category = "Restricted elevation"
        if rom_ratio > 0.85 and smoothness_score > 75:
            category = "Functional progression"
        elif rom_ratio < 0.5:
            category = "Marked motion limitation"

        return {
            "type": "RULE_BASED_DEMONSTRATION_ONLY",
            "disclaimer": "This demonstration score is a simple arithmetic heuristic. It is NOT an ML prediction or a clinical diagnosis.",
            "heuristic_score": heuristic_score,
            "demonstration_category": category
        }

ml_classifier = MovementQualityClassifier()
