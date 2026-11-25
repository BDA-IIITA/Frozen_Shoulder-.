# SPARS9x flexion monitoring — ten-participant pilot

For the current 20-participant model, replay and run commands, see [SPARS9x replay](spars9x-replay.md). The counts below document the earlier pilot.

This pipeline compares wrist measurements from active shoulder flexion with a reference learned from healthy SPARS9x participants. It also records session measurements from wrist vectors and, when paired orientation is available, from chest and limb quaternions. The score is a signed distance from the learned One-Class SVM boundary. It has no probability or clinical recovery interpretation.

## Install and reproduce

From the repository root with Python 3.12 and Node.js/npm available:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
npm --prefix frontend ci
```

Place the ten supplied `spars9x_s*.csv` files in `dataset/`. Keep their original names. Processing is local and can run without network access after installation.

```sh
cd backend
../.venv/bin/python -m app.services.flexion.offline process
../.venv/bin/python -m app.services.flexion.offline train
../.venv/bin/python -m app.services.flexion.offline evaluate
../.venv/bin/python -m pytest -q
```

Run `npm --prefix frontend run build` from the root to check TypeScript and build the frontend. The evaluation below ran on Python 3.12 with NumPy 2.5.1, SciPy 1.18.0, pandas 3.0.5, scikit-learn 1.9.0, joblib 1.5.3 and matplotlib 3.11.1. An artifact is accepted by the backend only with the same scikit-learn version and preprocessing schema that produced it. Retrain in the serving environment or install the recorded version. Set `FLEXION_MODEL_PATH` before startup to override the default. Only load locally generated or trusted joblib artifacts.

Start each process in its own terminal at the repository root:

```sh
cd backend
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```sh
npm --prefix frontend run dev
```

Open [the local frontend](http://localhost:5173), choose **Live Monitoring**, **Demo Generator**, and **Shoulder Flexion**, then start a session. Let it run for at least five seconds for a complete demonstration window. The page displays synthetic exercise telemetry, estimated repetitions, reference status and wrist/chest metrics. Use **Finish & Save**, then open **Rehabilitation Sessions** or **Progress Analytics**. The synthetic flexion demo supplies vectors and orientation at nominal 50 Hz. Start a second session on the same side for a comparison. With an absent model, the demo still measures and saves movement with an unavailable reference status.

## Dataset exploration

The original study describes wrist accelerometry, magnetometry and gyroscopy sampled at nominal 50 Hz in a 20-person healthy cohort. This checkout has ten participant files, which are the split groups used here. The source CSV has no timestamp column, so row positions give relative time at 20 ms per sample and cannot reveal gaps within otherwise unchanged rows. The paper identifies the IEEE release, and a published analysis of that release gives the original label mapping, including 8 for active flexion. The IEEE landing page was inaccessible during verification. [Original SPARS9x study](https://www.mdpi.com/1424-8220/21/5/1669) · [IEEE release DOI](https://doi.org/10.21227/cx5v-vw46) · [Published label mapping](https://www.mdpi.com/2073-431X/15/9/595)

The local files contain twelve headerless numeric columns. The observed ranges support the supplied ordering. Columns 0–2 show gravity-scale accelerations and are treated as m/s². Columns 3–5 are treated as magnetic field in µT, columns 6–8 as gyroscope values in rad/s, and column 9 as heart rate in bpm. Columns 10 and 11 are discrete side and activity codes. The parser preserves side codes as supplied because left/right assignments for 1 and 2 were unavailable in the documentation accessed. Code 0 occurred exclusively with activity 0. Heart rate ranged from 44 to 203. Acceleration and gyroscope per-axis extrema across all axes were approximately −72.14 to 60.87 m/s² and −29.28 to 30.11 rad/s. The magnetic channels have large excursions and are excluded along with heart rate.

The full scan counted **12,670,441 rows** and **210 contiguous same-side/same-label runs**. This included 200 labeled activity runs, 20 flexion bouts and 10 background runs. There were 200 label transitions within files. No column had a NaN or infinity, and no wrist row exceeded the broad input sanity bounds of ±200 m/s² and ±40 rad/s per axis. These limits catch grossly implausible inputs. They do not verify sensor calibration or magnetic anomalies.

| Activity code | Rows | Contiguous runs |
| --- | ---: | ---: |
| 0 | 12,253,018 | 10 |
| 1 | 38,251 | 20 |
| 2 | 45,460 | 20 |
| 3 | 37,214 | 20 |
| 4 | 37,066 | 20 |
| 5 | 37,263 | 20 |
| 6 | 43,236 | 20 |
| 7 | 45,177 | 20 |
| 8 | 42,840 | 20 |
| 9 | 50,151 | 20 |
| 10 | 40,765 | 20 |

Side codes 0, 1 and 2 had 12,253,018, 188,393 and 229,030 rows respectively. Flexion had 9 bouts with side code 1 and 11 with code 2. The most common transitions followed the repeated exercise order from 8 through 7, 9, 6, 1, 3, 5, 4, 10 and 2. One 4→8 transition interrupted that order. Each participant file had one label-0 background run. The JSON report records file-level counts, all transition pairs, ranges and missing values.

## Processing and segmentation

- The CSV scanner reads 100,000 rows per chunk. It retains at most a chunk and the selected contiguous bout being assembled. Subject, side, activity and zero-based original positions are preserved. Changes in side or activity, invalid wrist rows and file changes terminate a bout. Invalid rows are dropped without interpolation.
- A fourth-order Butterworth low-pass uses second-order sections at 5 Hz. The offline bout and model-window paths apply forward/backward zero-phase filtering on spans of at least 16 samples. The shared module supports causal filtering with explicit state, initialized to the first sample's steady state. Reset that state at boundaries. The app buffers complete windows and uses the same zero-phase processing as training, so a score appears after a window finishes.
- Acceleration magnitude shows dynamic movement around the gravity-scale signal. Gyroscope magnitude shows distinct bursts around movement phases. For exploratory repetition boundaries the segmenter uses the direction of filtered acceleration relative to a quiet start, checks a prominent peak of at least 40°, requires a return within 15°, and checks gyroscope motion and a 1–12 s span. It found 49 candidates across only four of the ten participants. Some bouts had rhythmic motion and no stable initial reference. The release has no annotated per-repetition boundaries for scoring the detector. Candidate counts are experimental.
- The reference model uses non-overlapping 200-sample windows anchored at each valid bout start. Partial windows are discarded. Each window is filtered independently, including in live inference. Other concentric exercises supply OOD comparisons. A deterministic probe samples up to one four-second window per 5,000 original rows from the label-0 background without crossing that run's bounds.
- The ordered feature schema includes acceleration magnitude mean, population SD and RMS in m/s², gyroscope magnitude mean, RMS, maximum and population SD in rad/s, sample-count duration in seconds and vector jerk RMS in m/s³. Jerk is the norm of the first difference of filtered acceleration divided by 20 ms, aggregated by RMS. It includes acceleration changes from changing gravity direction and is specific to this filtering and placement. Magnitude RMS and maximum describe complementary typical and peak speed; gyroscope SD captures variability. Duration is four seconds for every model window and only varies in the exploratory repetition features. IDs, side, magnetometer and heart rate are excluded from the predictors.

## Evaluation

The scaler and RBF One-Class SVM were fit only on the six training participants. Sixteen `nu` and `gamma` combinations were compared using flexion acceptance on the two validation participants. The search maximized window-level validation acceptance, breaking ties in grid order. The selected settings were `nu=0.01` and `gamma=0.01`. Test results are for two held-out participants, s5 and s6. OOD probes were evaluated on those same held-out participants.

| Evaluation subset | Accepted / total | Acceptance |
| --- | ---: | ---: |
| Healthy flexion, train | 122 / 124 | 98.39% |
| Healthy flexion, validation | 39 / 42 | 92.86% |
| Healthy flexion, test | 37 / 38 | 97.37% |
| Other labeled exercises, test | 47 / 220 | 21.36% |
| Sampled unstructured background, test | 151 / 624 | 24.20% |

Test subject s5 contributed 23/23 accepted flexion windows and s6 contributed 14/15. Multiple windows come from each participant, so the 38 test windows do not represent 38 independent people. Other movements sometimes pass the flexion reference. The model is intended for sessions already designated as flexion.

## Outputs and integration

| Output under `artifacts/flexion/` | Contents |
| --- | --- |
| `dataset_report.json` | Per-participant inspection and transitions |
| `recordings/*.npz` | Raw and bout-filtered six-axis label-8 recordings and metadata |
| `signals_*.png` | Per-bout raw/filtered magnitudes, tilt proxy when available and candidate boundaries |
| `repetitions.csv` | Exploratory start, peak and exclusive end indices and repetition features |
| `features.csv` | Fixed-window features and original row position metadata |
| `flexion.joblib`, `model_config.json` | Model pipeline, feature contract, versions, split and search results |
| `evaluation.json`, `evaluation.png` | Counts by split, test exercises, and score distributions |

The raw directory and generated artifacts are ignored by Git. The original firmware was left untouched. Existing HTTP/WebSocket paths are retained. The backend adds `analytics` to live samples and `movement_analytics` to saved sessions, history and reports. A separate database table is created at startup so existing rows stay readable. Historical rows without the new measurement metadata are unavailable for qualified excursion trends. Synthetic fixtures remain labeled as demo. Legacy numeric fields remain in the API for existing clients, including the zero placeholder when the angle is unavailable. For new consumers, use the nullable analytics values and sample quality flag.

- Use `sensors.wrist.accelerometer` and `sensors.wrist.gyroscope` with numeric `x`, `y` and `z` components, gravity-inclusive m/s² and rad/s. A device timestamp in seconds can be epoch time or elapsed time as long as it is monotonic. The wrist path requires 200 consecutive samples at near-50 Hz. Adjacent spacing must be 14–26 ms and the full elapsed time must be within 80 ms of 3.98 s. Invalid vectors, timing discontinuities and device changes reset continuity. The existing orientation-only `upper_arm` protocol still supplies legacy orientation display but cannot score the model from quaternions alone.
- An optional `sensors.wrist.quaternion` and synchronized `sensors.chest.quaternion` enable a chest-relative wrist excursion and threshold repetition estimates. The older paired `upper_arm` quaternion path retains its own label. For live hardware, the calibration button can capture a neutral offset from a recent paired packet before starting the session. Offsets are held in memory per device, source and limb protocol. Chest peak rotation is the sign-invariant quaternion displacement from the first chest sample and includes rotation in any direction. Either relative angle is a sensor proxy. Wrist rotation, elbow motion, mounting alignment and Euler-angle ambiguity can affect it. Anatomical glenohumeral ROM requires separately validated measurement. Where orientation and valid wrist vectors overlap a complete estimated repetition, the app also emits repetition features. SVM predictions still use four-second windows.
- Session movement duration sums completed estimated repetition spans. Gyro statistics and pooled jerk summarize complete wrist windows. Consistency uses repetition-duration and peak-angle SD once at least two estimates exist. The app stores score counts, signed scores and the latest SVM prediction (1 for within reference, −1 for outlier). Excursion comparisons require matching exercise, side, source and angle protocol.
- Use one server worker for the current in-memory active capture and one monitored session at a time. Finishing persists the analytics, while an interrupted process can leave an unfinished database session that can be discarded. The existing pause control pauses the display timer. Sensor capture continues.

The Python tests cover CSV layout and missing data, activity selection, chunk and timing boundaries, filter attenuation and causal state, candidate repetition completion, physical-unit features, participant splits, joblib inference parity, missing model and sensor behavior, and HTTP/WebSocket persistence. A headless Chrome smoke test completed a synthetic flexion session, observed the live model score, saved the session and located it in the excursion trend. Real BNO086 mounting, packet fields and cadence, repetition ground truth, anatomy, and use by patients remain to be validated.
