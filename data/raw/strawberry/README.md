---
license: cc-by-4.0
configs:
- config_name: default
  data_files:
  - split: s1
    path: data/s1-*
  - split: s2
    path: data/s2-*
  - split: s3
    path: data/s3-*
  - split: s4
    path: data/s4-*
  - split: s5
    path: data/s5-*
  - split: s6
    path: data/s6-*
dataset_info:
  features:
  - name: Time
    dtype: string
  - name: Front_Top
    dtype: float32
  - name: Front_Middle
    dtype: float32
  - name: Front_Bottom
    dtype: float32
  - name: Middle_Top
    dtype: float32
  - name: Middle_Middle
    dtype: float32
  - name: Middle_Bottom
    dtype: float32
  - name: Rear_Top
    dtype: float32
  - name: Rear_Middle
    dtype: float32
  - name: Rear_Bottom
    dtype: float32
  - name: N_valid
    dtype: int32
  - name: coverage_points
    dtype: float32
  - name: N_active_t
    dtype: int32
  - name: coverage_time
    dtype: float32
  - name: T_max_window
    dtype: float32
  - name: T_min_window
    dtype: float32
  - name: T_mean
    dtype: float32
  - name: T_std
    dtype: float32
  - name: dur_gt4
    dtype: int32
  - name: dur_lt0
    dtype: int32
  - name: dur_lt_minus1
    dtype: int32
  - name: has_over10
    dtype: int32
  - name: risk_level
    dtype:
      class_label:
        names:
          '0': R0
          '1': R1
          '2': R2
  - name: conf_level
    dtype:
      class_label:
        names:
          '0': low
          '1': medium
          '2': high
  - name: cause_high_peak
    dtype: int32
  - name: cause_high_duration
    dtype: int32
  - name: cause_low_peak
    dtype: int32
  - name: cause_low_duration
    dtype: int32
  - name: label_R0
    dtype: int32
  - name: label_R1
    dtype: int32
  - name: label_R2
    dtype: int32
  - name: window_id
    dtype: int32
  - name: window_start_time
    dtype: string
  - name: window_end_time
    dtype: string
  - name: shipment_id
    dtype: string
  - name: summary_text
    dtype: string
  - name: driver_message
    dtype: string
  splits:
  - name: s1
    num_bytes: 2614134
    num_examples: 3146
  - name: s2
    num_bytes: 2383842
    num_examples: 2616
  - name: s3
    num_bytes: 1952989
    num_examples: 2162
  - name: s4
    num_bytes: 2051974
    num_examples: 2162
  - name: s5
    num_bytes: 1916501
    num_examples: 2039
  - name: s6
    num_bytes: 2182435
    num_examples: 2273
  download_size: 1256937
  dataset_size: 13101875
---

# Cold-Chain Strawberry Multi-Sensor Dataset (Shipments S1–S6)

This repository provides a processed multi-shipment cold-chain dataset for fresh strawberries. It supports research on human-centric cold-chain transportation monitoring, interpretable rule-based risk assessment, and small language model (SLM) generation of driver-facing alert messages.

The dataset accompanies the following article:

> Li, H., Uygun, Ö., Yu, X., Zhou, Y., Yang, Z., & Chen, C.-H. (2026). *A Human-Centric Decision Support Framework for Edge-Based Cold Chain Transportation Monitoring with Small Language Models*. Computers & Industrial Engineering, 112240. https://doi.org/10.1016/j.cie.2026.112240

## Dataset Overview

The dataset contains:

- **10-minute resolution** temperature measurements from 9 sensors inside refrigerated trucks
- **1-hour sliding windows** with engineered features and rule-based risk labels
- **Structured risk annotations**, including risk level, confidence level, and cause indicators
- **Natural-language summaries** (`summary_text`) describing each monitoring window
- **Four-line driver-facing messages** (`driver_message`) for SLM training and evaluation

The source data are derived from the public strawberry cold-chain dataset by Abdella et al. (2021). The released files in this repository provide processed, aligned, and annotated data for the strawberry cold-chain monitoring case study.

## Files and Splits

The main loadable dataset is organized as six Hugging Face dataset splits, one per shipment:

- `s1`
- `s2`
- `s3`
- `s4`
- `s5`
- `s6`

In the repository file structure, these splits are stored under the `data/` folder as Hugging Face-compatible split files:

- `data/s1-00000-of-00001.parquet`
- `data/s2-00000-of-00001.parquet`
- `data/s3-00000-of-00001.parquet`
- `data/s4-00000-of-00001.parquet`
- `data/s5-00000-of-00001.parquet`
- `data/s6-00000-of-00001.parquet`

Each split contains:

- Time-aligned, strictly 10-minute sampled sensor data
- 1-hour window-level features
- Rule-based risk labels and cause indicators
- A machine-generated `summary_text`
- A short 4-line `driver_message` with operational guidance

In the associated article, the target output is referred to as the reference message. In this released dataset, the corresponding column is named `driver_message`.

## Sample Counts

The released split files contain both 10-minute rows and 1-hour sliding-window records. The first five rows of each shipment do not yet form a complete 1-hour window.

| Shipment | Released rows | 1-hour windows / text pairs | Role |
|---|---:|---:|---|
| S1 | 3,146 | 3,141 | Test |
| S2 | 2,616 | 2,611 | Test |
| S3 | 2,162 | 2,157 | Training |
| S4 | 2,162 | 2,157 | Test |
| S5 | 2,039 | 2,034 | Test |
| S6 | 2,273 | 2,268 | Test |
| **Total** | **14,398** | **14,368** | — |

The training split uses shipment **S3** with **2,157** one-hour windows. The held-out test split uses shipments **S1, S2, S4, S5, and S6**, comprising **12,211** one-hour windows.

## Hugging Face Datasets Usage

The dataset can be loaded using the Hugging Face `datasets` library:

```python
from datasets import load_dataset

ds = load_dataset("NifferLi/cold-chain-strawberry-sensors")

print(ds.keys())        # dict_keys(['s1', 's2', 's3', 's4', 's5', 's6'])

row = ds["s3"][100]
print(row["Time"], row["shipment_id"], row["risk_level"])
print(row["summary_text"])
print(row["driver_message"])
```

Each split (`s1`–`s6`) corresponds to one shipment and follows the same schema.

## Data Schema

Each row represents:

1. A single **10-minute time step** with raw sensor readings, and
2. The **1-hour sliding window** ending at that time step.

For row index `i >= 5`, the 1-hour window covers time steps `i-5, ..., i`, corresponding to 6 time points at 10-minute resolution.

### 1. Time and Metadata

| Column | Description |
|---|---|
| `Time` | Timestamp of the 10-minute time step after resampling. |
| `window_id` | Integer ID of the 1-hour sliding window. The first complete window has `window_id = 0`. |
| `window_start_time` | Start time of the 1-hour window. |
| `window_end_time` | End time of the 1-hour window. |
| `shipment_id` | Shipment identifier: `S1`, `S2`, ..., `S6`. |

### 2. Raw Sensor Readings

The dataset includes 9 temperature sensors arranged across three longitudinal positions and three vertical levels:

| Column | Description |
|---|---|
| `Front_Top` | Temperature at front-top sensor. |
| `Front_Middle` | Temperature at front-middle sensor. |
| `Front_Bottom` | Temperature at front-bottom sensor. |
| `Middle_Top` | Temperature at middle-top sensor. |
| `Middle_Middle` | Temperature at middle-middle sensor. |
| `Middle_Bottom` | Temperature at middle-bottom sensor. |
| `Rear_Top` | Temperature at rear-top sensor. |
| `Rear_Middle` | Temperature at rear-middle sensor. |
| `Rear_Bottom` | Temperature at rear-bottom sensor. |

All temperatures are in degrees Celsius (°C), converted from the original Fahrenheit readings. Missing measurements, such as sensor dropouts or gaps longer than 30 minutes, are represented as `NaN`.

### 3. Window-Level Coverage Features

Computed over each 1-hour window:

| Column | Description |
|---|---|
| `N_valid` | Number of non-missing sensor readings in the window. Maximum = 54, corresponding to 9 sensors × 6 time points. |
| `coverage_points` | Point-level coverage ratio, computed as `N_valid / 54`. |
| `N_active_t` | Number of time points in the window with at least one valid sensor reading. |
| `coverage_time` | Time-level coverage ratio, computed as `N_active_t / 6`. |

These features describe data completeness and support confidence-level assignment.

### 4. Window-Level Temperature Features

Computed over all valid sensor readings in the 1-hour window:

| Column | Description |
|---|---|
| `T_max_window` | Maximum observed temperature in the window. |
| `T_min_window` | Minimum observed temperature in the window. |
| `T_mean` | Mean temperature in the window. |
| `T_std` | Standard deviation of temperature in the window, reflecting thermal stability or spatial unevenness. |

### 5. Exposure Duration Features

Each time step corresponds to 10 minutes of exposure. Duration features are computed over the 1-hour window:

| Column | Description |
|---|---|
| `dur_gt4` | Total minutes where the row-wise maximum temperature exceeds 4.0°C. |
| `dur_lt0` | Total minutes where the row-wise minimum temperature is below 0.0°C. |
| `dur_lt_minus1` | Total minutes where the row-wise minimum temperature is below -1.0°C. |
| `has_over10` | Indicator for whether `T_max_window > 10.0°C`. |

### 6. Risk Labels

Risk labels are rule-based and designed for interpretable cold-chain monitoring.

#### Main risk level: `risk_level`

`risk_level` ∈ {0, 1, 2}:

- **0 = R0 / Normal**

  The window remains within the ideal strawberry cold-chain range:

  `T_max_window <= 4.0°C` and `T_min_window >= 0.0°C`.

- **2 = R2 / Severe risk**

  Assigned if any of the following conditions holds:

  - `T_max_window > 10.0°C`
  - `dur_gt4 >= 30` minutes
  - `T_min_window < -1.0°C`
  - `dur_lt0 >= 30` minutes

- **1 = R1 / Mild risk**

  Assigned to all remaining cases that are neither R0 nor R2.

The one-hot columns `label_R0`, `label_R1`, and `label_R2` indicate the corresponding risk level where applicable.

### 7. Confidence Level

The confidence level is based on data coverage:

| Column | Description |
|---|---|
| `conf_level` | 0 = low confidence, 1 = medium confidence, 2 = high confidence. |

The confidence score combines point-level coverage and time-level coverage:

```text
conf_score = (coverage_points + coverage_time) / 2
```

The confidence bands are:

- High confidence if `conf_score >= 0.8`
- Medium confidence if `0.5 <= conf_score < 0.8`
- Low confidence if `conf_score < 0.5`

When the window contains no valid sensor readings, the system uses a fail-safe message rather than a normal risk assessment.

### 8. Risk Cause Indicators

For R2 windows, the following binary cause indicators identify the source of severe risk:

| Column | Description |
|---|---|
| `cause_high_peak` | 1 if the window contains an extreme high-temperature peak. |
| `cause_high_duration` | 1 if the window has prolonged exposure above 4.0°C. |
| `cause_low_peak` | 1 if the window contains a temperature below -1.0°C. |
| `cause_low_duration` | 1 if the window has prolonged exposure below 0.0°C. |

These indicators help distinguish different operational risk patterns, such as short high-temperature peaks, prolonged warming, near-freezing conditions, and prolonged cold exposure.

### 9. Natural-Language Fields

| Column | Description |
|---|---|
| `summary_text` | A structured natural-language summary of the 1-hour window, generated from computed features and labels. |
| `driver_message` | A short 4-line driver-facing alert message used as target text for SLM training and evaluation. |

The `driver_message` follows a fixed four-line structure:

```text
Line 1: Status: ...
Line 2: Temp pattern: ...
Line 3: Data quality: ...
Line 4: Action: ...
```

The message is intended to convert structured sensor and risk information into concise operational guidance for refrigerated-truck drivers.

## Preprocessing Summary

The preprocessing pipeline includes:

- Conversion of original temperature readings from Fahrenheit to Celsius
- Temporal alignment to a strict 10-minute grid
- Linear interpolation for acceptable gaps
- Marking gaps longer than 30 minutes as `NaN`
- Construction of 1-hour sliding windows
- Computation of window-level temperature, duration, and coverage features
- Assignment of rule-based risk labels, confidence levels, and cause flags
- Generation of `summary_text` and `driver_message` fields for SLM-based explanation tasks

## Typical Research Uses

This dataset can support several tasks:

### 1. Window-Level Risk Classification

- **Input:** raw sensor readings, engineered features, or both
- **Target:** `risk_level` or one-hot labels

### 2. Confidence Estimation

- **Input:** coverage features and sensor availability patterns
- **Target:** `conf_level`

### 3. Time-Series Anomaly Analysis

- Identify segments with severe risk
- Analyze high-temperature, low-temperature, and data-quality patterns

### 4. Human-Centric Explanation Generation

- **Input:** `summary_text`
- **Target:** `driver_message`

This task supports research on SLMs that transform structured cold-chain monitoring summaries into short, actionable driver alerts.

## Limitations

- The dataset covers six strawberry shipments and may not represent all products, vehicle types, routes, or cold-chain operating conditions.
- Risk labels are rule-based and reflect the strawberry-specific thresholds used in the associated study.
- The dataset focuses on temperature monitoring; additional sensor modalities such as humidity, vibration, and door-state sensing are not included.
- The released driver-facing messages are designed for research and evaluation, not direct deployment without operational validation.

## License

This dataset is released under the **CC BY 4.0** (Creative Commons Attribution 4.0 International) license.

## Citation

If you use this dataset, please cite the associated article:

```bibtex
@article{li2026human_centric_decision_support_cold_chain_slm,
  title   = {A Human-Centric Decision Support Framework for Edge-Based Cold Chain Transportation Monitoring with Small Language Models},
  author  = {Li, H. and Uygun, {\"O}. and Yu, X. and Zhou, Y. and Yang, Z. and Chen, C.-H.},
  journal = {Computers \& Industrial Engineering},
  year    = {2026},
  pages   = {112240},
  doi     = {10.1016/j.cie.2026.112240}
}
```

You may also cite this dataset repository directly:

```bibtex
@dataset{li2026cold_chain_strawberry_sensors,
  title     = {Cold-Chain Strawberry Multi-Sensor Dataset for Human-Centric Edge Monitoring},
  author    = {Li, H. and Uygun, {\"O}. and Yu, X. and Zhou, Y. and Yang, Z. and Chen, C.-H.},
  year      = {2026},
  publisher = {Hugging Face},
  url       = {https://huggingface.co/datasets/NifferLi/cold-chain-strawberry-sensors}
}
```