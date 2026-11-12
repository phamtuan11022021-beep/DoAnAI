from __future__ import annotations

import json
import math
import sys
from copy import deepcopy
from pathlib import Path

import pandas as pd

try:
    import joblib
    import numpy as np
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import (
        GradientBoostingRegressor,
        RandomForestRegressor,
    )
    from sklearn.linear_model import Ridge
    from sklearn.metrics import (
        mean_absolute_error,
        mean_squared_error,
        r2_score,
    )
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import (
        OneHotEncoder,
        StandardScaler,
    )
except ImportError as exc:
    print("Thiếu thư viện ML:", exc)
    print(
        "Chạy: python -m pip install scikit-learn joblib"
    )
    sys.exit(1)


# =============================================================================
# UniConnect AI - TRAIN + TEMPORAL EVALUATION
# =============================================================================
#
# Evaluation:
#   TRAIN targets : 2024 + 2025
#   TEST holdout  : 2026
#
# Sau khi đánh giá:
#   fit lại best ML model trên all supervised targets 2024-2026
#   rồi dự đoán 2027.
#
# Không random split vì bài toán là dự báo theo thời gian.
# =============================================================================

ROOT_DIR = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT_DIR / "data" / "dataset"
MODEL_DIR = ROOT_DIR / "ai" / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_FILE = (
    DATASET_DIR / "admission_scores_train_features_2024_2025.csv"
)
TEST_FILE = (
    DATASET_DIR / "admission_scores_test_features_2026.csv"
)
ALL_FEATURES_FILE = (
    DATASET_DIR / "admission_scores_2023_2026_model_features.csv"
)
PREDICT_2027_FILE = (
    DATASET_DIR / "admission_scores_predict_features_2027.csv"
)

METRICS_FILE = (
    DATASET_DIR / "cutoff_model_metrics_2026_holdout.csv"
)
TEST_PRED_FILE = (
    DATASET_DIR / "cutoff_predictions_2026_holdout.csv"
)
PRED_2027_OUTPUT = (
    DATASET_DIR / "predicted_cutoff_2027.csv"
)
MODEL_FILE = (
    MODEL_DIR / "best_cutoff_model.joblib"
)
MODEL_META_FILE = (
    MODEL_DIR / "best_cutoff_model_metadata.json"
)

NUMERIC_FEATURES = [
    "target_year",
    "history_count",
    "first_year",
    "last_year",
    "gap_years",
    "history_span",
    "last_score",
    "prev2_score",
    "mean_score",
    "min_score",
    "max_score",
    "std_score",
    "trend_per_year",
    "last_delta_per_year",
    "last_combination_count",
    "last_combination_known",
]

CATEGORICAL_FEATURES = [
    "university_key",
    "major_group",
]

MODEL_FEATURES = (
    NUMERIC_FEATURES
    + CATEGORICAL_FEATURES
)

TARGET = "cutoff_score"


def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"Thiếu file: {path}"
        )


def load_feature_file(
    path: Path,
    *,
    require_target: bool,
) -> pd.DataFrame:
    require_file(path)

    df = pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
    )

    required = (
        MODEL_FEATURES
        + [
            "program_key",
            "university_name",
            "major_name",
            "major_code_key",
        ]
    )

    if require_target:
        required += [TARGET]

    missing = [
        col
        for col in required
        if col not in df.columns
    ]

    if missing:
        raise RuntimeError(
            f"{path.name} thiếu cột: {missing}"
        )

    for col in NUMERIC_FEATURES:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    if require_target:
        df[TARGET] = pd.to_numeric(
            df[TARGET],
            errors="coerce",
        )

    if df[NUMERIC_FEATURES].isna().any().any():
        raise RuntimeError(
            f"{path.name}: numeric feature NaN."
        )

    if (
        require_target
        and df[TARGET].isna().any()
    ):
        raise RuntimeError(
            f"{path.name}: target NaN."
        )

    return df


def make_onehot():
    try:
        return OneHotEncoder(
            handle_unknown="ignore",
            sparse_output=False,
        )
    except TypeError:
        # scikit-learn < 1.2 compatibility.
        return OneHotEncoder(
            handle_unknown="ignore",
            sparse=False,
        )


def make_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            (
                "num",
                StandardScaler(),
                NUMERIC_FEATURES,
            ),
            (
                "cat",
                make_onehot(),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
    )


def clip_scores(values):
    return np.clip(
        np.asarray(values, dtype=float),
        10.0,
        30.0,
    )


def metric_record(
    name: str,
    y_true,
    y_pred,
) -> dict:
    y_true = np.asarray(
        y_true,
        dtype=float,
    )
    y_pred = clip_scores(
        y_pred
    )

    errors = np.abs(
        y_true - y_pred
    )

    return {
        "method":
            name,
        "mae":
            float(
                mean_absolute_error(
                    y_true,
                    y_pred,
                )
            ),
        "rmse":
            float(
                math.sqrt(
                    mean_squared_error(
                        y_true,
                        y_pred,
                    )
                )
            ),
        "r2":
            float(
                r2_score(
                    y_true,
                    y_pred,
                )
            ),
        "within_1_point":
            float(
                np.mean(
                    errors <= 1.0
                )
            ),
        "within_2_points":
            float(
                np.mean(
                    errors <= 2.0
                )
            ),
        "n_test":
            int(
                len(y_true)
            ),
    }


def build_models() -> dict[str, Pipeline]:
    return {
        "Ridge": Pipeline(
            [
                (
                    "prep",
                    make_preprocessor(),
                ),
                (
                    "model",
                    Ridge(
                        alpha=10.0
                    ),
                ),
            ]
        ),
        "RandomForest": Pipeline(
            [
                (
                    "prep",
                    make_preprocessor(),
                ),
                (
                    "model",
                    RandomForestRegressor(
                        n_estimators=500,
                        max_depth=14,
                        min_samples_leaf=2,
                        max_features=0.75,
                        random_state=42,
                        n_jobs=-1,
                    ),
                ),
            ]
        ),
        "GradientBoosting": Pipeline(
            [
                (
                    "prep",
                    make_preprocessor(),
                ),
                (
                    "model",
                    GradientBoostingRegressor(
                        n_estimators=350,
                        learning_rate=0.03,
                        max_depth=2,
                        min_samples_leaf=3,
                        loss="huber",
                        random_state=42,
                    ),
                ),
            ]
        ),
    }


def baseline_predictions(
    df: pd.DataFrame,
) -> dict[str, np.ndarray]:
    last = df[
        "last_score"
    ].astype(float).to_numpy()

    trend = (
        last
        + df[
            "trend_per_year"
        ].astype(float).to_numpy()
        * df[
            "gap_years"
        ].astype(float).to_numpy()
    )

    return {
        "Baseline_LastScore":
            clip_scores(last),
        "Baseline_Trend":
            clip_scores(trend),
    }


def main() -> None:
    print("=" * 118)
    print("UNICONNECT AI - TRAIN / TEMPORAL HOLDOUT 2026 / PREDICT 2027")
    print("=" * 118)

    train = load_feature_file(
        TRAIN_FILE,
        require_target=True,
    )

    test = load_feature_file(
        TEST_FILE,
        require_target=True,
    )

    all_features = load_feature_file(
        ALL_FEATURES_FILE,
        require_target=True,
    )

    predict_2027 = load_feature_file(
        PREDICT_2027_FILE,
        require_target=False,
    )

    if train.empty:
        raise RuntimeError(
            "Train dataset rỗng."
        )

    if test.empty:
        raise RuntimeError(
            "2026 holdout dataset rỗng."
        )

    # Hard temporal audit.
    if (
        train[
            "target_year"
        ] >= 2026
    ).any():
        raise RuntimeError(
            "LEAKAGE: train chứa target >= 2026."
        )

    if not (
        test[
            "target_year"
        ] == 2026
    ).all():
        raise RuntimeError(
            "TEST phải chỉ chứa target 2026."
        )

    # Select on 2025 only; never choose a model using the 2026 test labels.
    selection_train = train[train["target_year"].eq(2024)]
    validation = train[train["target_year"].eq(2025)]
    if selection_train.empty or validation.empty:
        raise RuntimeError("Need both 2024 training and 2025 validation rows.")
    validation_metrics = [
        metric_record(name, validation[TARGET], values)
        for name, values in baseline_predictions(validation).items()
    ]
    for name, candidate in build_models().items():
        print(f"Validation 2025: {name} ...", flush=True)
        candidate.fit(selection_train[MODEL_FEATURES], selection_train[TARGET])
        validation_metrics.append(metric_record(
            name, validation[TARGET], candidate.predict(validation[MODEL_FEATURES])))
    selection = pd.DataFrame(validation_metrics).sort_values(["mae", "rmse"])
    selection.to_csv(DATASET_DIR / "cutoff_model_validation_2025.csv", index=False, encoding="utf-8-sig")
    selected_overall = str(selection.iloc[0]["method"])
    selected_ml = str(selection[~selection.method.str.startswith("Baseline_")].iloc[0]["method"])

    X_train = train[
        MODEL_FEATURES
    ]
    y_train = train[
        TARGET
    ].astype(float)

    X_test = test[
        MODEL_FEATURES
    ]
    y_test = test[
        TARGET
    ].astype(float)

    metrics = []
    test_prediction_columns = {}

    # -------------------------------------------------------------------------
    # Baselines
    # -------------------------------------------------------------------------
    baselines = baseline_predictions(
        test
    )

    for name, prediction in baselines.items():
        metrics.append(
            metric_record(
                name,
                y_test,
                prediction,
            )
        )
        test_prediction_columns[
            name
        ] = prediction

    # -------------------------------------------------------------------------
    # ML models
    # -------------------------------------------------------------------------
    fitted_models = {}

    for name, pipeline in build_models().items():
        print(
            f"Training {name} ...",
            flush=True,
        )

        pipeline.fit(
            X_train,
            y_train,
        )

        prediction = clip_scores(
            pipeline.predict(
                X_test
            )
        )

        metrics.append(
            metric_record(
                name,
                y_test,
                prediction,
            )
        )

        test_prediction_columns[
            name
        ] = prediction

        fitted_models[
            name
        ] = pipeline

    metrics_df = pd.DataFrame(
        metrics
    ).sort_values(
        [
            "mae",
            "rmse",
        ],
        ascending=[
            True,
            True,
        ],
    ).reset_index(
        drop=True
    )

    best_overall = selected_overall
    best_ml = selected_ml

    # -------------------------------------------------------------------------
    # Save holdout predictions.
    # -------------------------------------------------------------------------
    output = test[
        [
            "program_key",
            "university_name",
            "major_code_key",
            "major_name",
            "target_year",
            "last_year",
            "last_score",
            TARGET,
            "target_eligible_combinations",
        ]
    ].copy()

    output = output.rename(
        columns={
            TARGET:
                "actual_cutoff_2026"
        }
    )

    for name, prediction in test_prediction_columns.items():
        output[
            f"pred_{name}"
        ] = prediction

    output.to_csv(
        TEST_PRED_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    metrics_df.to_csv(
        METRICS_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    # -------------------------------------------------------------------------
    # Refit BEST ML on every supervised row available through target 2026.
    # -------------------------------------------------------------------------
    all_train = all_features[
        all_features[
            "target_year"
        ].between(
            2024,
            2026,
        )
    ].copy()

    best_pipeline = build_models()[
        best_ml
    ]

    best_pipeline.fit(
        all_train[
            MODEL_FEATURES
        ],
        all_train[
            TARGET
        ].astype(float),
    )

    joblib.dump(
        best_pipeline,
        MODEL_FILE,
    )

    # -------------------------------------------------------------------------
    # Predict 2027.
    # -------------------------------------------------------------------------
    ml_pred_2027 = clip_scores(
        best_pipeline.predict(
            predict_2027[
                MODEL_FEATURES
            ]
        )
    )

    baseline_2027 = baseline_predictions(
        predict_2027
    )

    pred_2027 = predict_2027[
        [
            "program_key",
            "university_name",
            "major_code_key",
            "major_name",
            "target_year",
            "history_count",
            "last_year",
            "last_score",
            "mean_score",
            "trend_per_year",
            "last_eligible_combinations",
        ]
    ].copy()

    pred_2027[
        f"prediction_{best_ml}"
    ] = ml_pred_2027
    pred_2027[
        "prediction_Baseline_LastScore"
    ] = baseline_2027[
        "Baseline_LastScore"
    ]
    pred_2027[
        "prediction_Baseline_Trend"
    ] = baseline_2027[
        "Baseline_Trend"
    ]

    if best_overall == "Baseline_LastScore":
        selected = baseline_2027[
            "Baseline_LastScore"
        ]
    elif best_overall == "Baseline_Trend":
        selected = baseline_2027[
            "Baseline_Trend"
        ]
    else:
        # Best overall ML model might differ from best_ml only if the
        # table changed; normally this equals best_ml.
        final_model = build_models()[
            best_overall
        ]

        final_model.fit(
            all_train[
                MODEL_FEATURES
            ],
            all_train[
                TARGET
            ].astype(float),
        )

        selected = clip_scores(
            final_model.predict(
                predict_2027[
                    MODEL_FEATURES
                ]
            )
        )

    pred_2027[
        "predicted_cutoff_2027"
    ] = selected

    # Keep predictions readable.
    prediction_cols = [
        col
        for col in pred_2027.columns
        if col.startswith(
            "prediction_"
        )
        or col == "predicted_cutoff_2027"
    ]

    for col in prediction_cols:
        pred_2027[col] = (
            pd.to_numeric(
                pred_2027[col],
                errors="coerce",
            )
            .round(2)
        )

    pred_2027.to_csv(
        PRED_2027_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    metadata = {
        "evaluation_design":
            "select on validation 2025 after training 2024; refit 2024-2025; test once on 2026",
        "deployment_target":
            2027,
        "best_ml_model":
            best_ml,
        "best_overall_method":
            best_overall,
        "train_rows_2024_2025":
            len(train),
        "test_rows_2026":
            len(test),
        "refit_rows_2024_2026":
            len(all_train),
        "predicted_programs_2027":
            len(pred_2027),
        "features":
            MODEL_FEATURES,
        "model_file":
            str(MODEL_FILE),
    }

    MODEL_META_FILE.write_text(
        json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # -------------------------------------------------------------------------
    # Terminal summary.
    # -------------------------------------------------------------------------
    print()
    print("=" * 118)
    print("KẾT QUẢ TEMPORAL EVALUATION 2026")
    print("=" * 118)

    display = metrics_df.copy()

    for col in (
        "mae",
        "rmse",
        "r2",
        "within_1_point",
        "within_2_points",
    ):
        display[col] = display[
            col
        ].map(
            lambda value: round(
                float(value),
                4,
            )
        )

    print(
        display.to_string(
            index=False
        )
    )

    print("-" * 118)
    print(
        f"BEST ML MODEL          : {best_ml}"
    )
    print(
        f"BEST OVERALL METHOD    : {best_overall}"
    )
    print(
        f"TRAIN ROWS 2024-2025   : {len(train)}"
    )
    print(
        f"TEST ROWS 2026         : {len(test)}"
    )
    print(
        f"REFIT ROWS 2024-2026   : {len(all_train)}"
    )
    print(
        f"PREDICTED 2027 PROGRAMS: {len(pred_2027)}"
    )
    print("-" * 118)
    print("METRICS       :", METRICS_FILE)
    print("TEST PRED     :", TEST_PRED_FILE)
    print("MODEL         :", MODEL_FILE)
    print("MODEL META    :", MODEL_META_FILE)
    print("PREDICT 2027  :", PRED_2027_OUTPUT)
    print("=" * 118)

    print()
    print(
        "MODEL CHECKPOINT       : ✅ TEMPORAL HOLDOUT 2026 ĐÃ ĐÁNH GIÁ; "
        "BEST ML ĐÃ REFIT ĐỂ DỰ ĐOÁN 2027"
    )


if __name__ == "__main__":
    main()
