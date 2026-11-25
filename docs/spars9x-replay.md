# SPARS9x replay and expanded-cohort evaluation

The offline pipeline and the app now use `artifacts/flexion-v2/` by default. The pilot artifacts remain in `artifacts/flexion/`. The v2 catalog has 240 wrist-only recordings across the six labeled concentric exercises. Active flexion has the fitted novelty reference and the exploratory cycle estimate. Other exercises are replayable with wrist telemetry and movement statistics.

## Run locally

From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
npm --prefix frontend ci
cd backend
../.venv/bin/python -m app.services.flexion.offline process
../.venv/bin/python -m app.services.flexion.offline train
../.venv/bin/python -m app.services.flexion.offline evaluate
../.venv/bin/python -m app.services.flexion.annotation coverage ../artifacts/flexion-v2/recordings
../.venv/bin/python -m app.services.flexion.annotation evaluate ../artifacts/flexion-v2/recordings ../docs/spars9x-cycle-review.csv
../.venv/bin/python -m pytest -q
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal at the repository root:

```sh
npm --prefix frontend run build
npm --prefix frontend run dev -- --host 127.0.0.1
```

Open [ShoulderSense](http://127.0.0.1:5173). Under **Live Monitoring → Dataset Replay**, select **s10** and the **27.4 s Active flexion** recording (`spars9x_s10_15108`). Start the session, wait for completion, then select **Finish & Save**. In **Progress Analytics**, select **SPARS9x replay** and the recorded participant and side. In **Rehabilitation Sessions**, the session details include the saved wrist signals and the sequence of model scores. This recording replayed 1,368 samples with six scored windows, five within reference and one outlier, and 20 estimated wrist cycles. The chest and excursion metrics were unavailable.

### Playback and progress screens

Live Monitoring opens in **Dataset Replay**. Choose a participant, exercise recording, and 1×, 2×, or 4× speed. Pause freezes the recorded position and preserves partially accumulated windows. Resume continues from that position. Restart clears the current unsaved measurements and starts the same recording from the beginning. All speeds retain 50 Hz sample timestamps for the detector and model. Finish & Save also accepts partial replays, which are labeled in the saved list and excluded from complete-recording trends.

The movement timeline shows estimated cycles and four-second reference checks on the recording clock. Raw wrist traces and the latest signed model score are under **Technical details**. Progress Analytics groups saved sessions by source, exercise, participant, and side. Replayed sessions describe recorded participants. Repeating the same recording reproduces the same data. Within-reference percentages use the number of scored windows as the denominator. They describe movement similarity. Chest-relative excursion and self-reported pain appear only when their measurements are available.

If the app is already running, restart the API after training so it loads the regenerated artifact. `FLEXION_MODEL_PATH` and `SPARS9X_RECORDINGS` override the joblib path and recordings directory. Use the same scikit-learn version at training and startup. Use `VITE_BACKEND_ORIGIN` if the API is served from a different origin.

## Dataset and repetition investigation

The scan found 22,884,160 rows across all 20 participants, including 83,874 active-flexion samples in 40 bouts. It found 420 contiguous side/label runs overall, zero NaNs or infinities and zero six-axis wrist rows outside the configured sanity bounds. Each flexion label-8 run covers a multi-cycle bout, including entry and exit motion. There are no per-repetition boundaries, count labels, synchronized chest data, or video in the supplied files. Original row positions give relative time at the nominal 50 Hz.

I inspected independent wrist acceleration and signed gyroscope traces across s0–s7. The legacy gravity-direction detector needed a quiet first half-second and a return near the initial pose. Ten of 40 bouts had no usable initial reference. Some other recordings contained sustained periodic motion around a pose far from the initial reference, with acceleration changes much smaller than its 40° gate. Gyroscope magnitude loses sign, so it can peak on both halves of a repetition. In the reviewed clips it sometimes doubled cycles or tracked a harmonic.

The selected experimental method projects the three gyro axes onto their dominant principal axis, uses a 0.18–2 Hz bandpass for cycle analysis, estimates the period via autocorrelation, and identifies adaptive, prominent cycles only when the period and the intervening opposite phase agree. It abstains without sufficient periodicity and two complete same-phase intervals. Boundaries indicate signal phase, and limb motion interpretation requires external ground truth. The online replay recomputes using only the prefix already streamed, with a final calculation at save. Provisional counts can change as more samples arrive. Hardware still uses the paired-orientation counter when available.

| Exploratory detector | Bouts with estimates | Candidate cycles |
| --- | ---: | ---: |
| Legacy quiet-start/return-to-rest thresholds | 11 / 40 | 67 |
| Signed gyroscope with periodicity | 35 / 40 | 664 |
| Gyroscope magnitude with periodicity | 20 / 40 | 392 |
| Acceleration with periodicity | 33 / 40 | 635 |

The three selected clips were reviewed from plots of the filtered axes without detector overlays. Same-phase landmarks were manually marked where both acceleration and the alternating gyro trace supported a cycle. Counts below are signed errors relative to those reviewer counts. Clear clips and visual acceleration landmarks favor the acceleration-based method. Signed gyro retained direction, estimated more full bouts, and had one more missed cycle on this small review. This is an exploratory signal review by one reviewer. It supplies neither anatomical repetition ground truth nor a clinical count-error estimate.

| Recording and clip | Reviewer cycles | Legacy error | Signed gyro error | Gyro magnitude error | Acceleration error |
| --- | ---: | ---: | ---: | ---: | ---: |
| s7, start row 0, 4–21 s | 12 | −12 | −1 | −6 | 0 |
| s2, start row 5177, 4–21 s | 7 | −7 | 0 | +5 | 0 |
| s5, start row 0, 8–24 s | 6 | −6 | 0 | −1 | 0 |

For an independent review, generate plots with:

```sh
cd backend
../.venv/bin/python -m app.services.flexion.annotation plot \
  ../artifacts/flexion-v2/recordings/spars9x_s7_0.npz /tmp/s7-review.png --start 4 --end 21
```

Mark equivalent phase landmarks in seconds, check both the acceleration shape and signed gyro direction, and leave uncertain clips unscored. Enter the clip bounds and ordered landmarks in the format of [the review CSV](spars9x-cycle-review.csv). Run the `annotation evaluate` command above. Use synchronized video or observer-counted repetitions for hardware and patient validation.

## One-Class SVM

Repetition-level boundaries were too weakly supported for model training. The fixed 200-sample non-overlapping windows, feature order, 5 Hz fourth-order zero-phase per-window filter, and gravity-inclusive acceleration / rad/s units were retained. The duration predictor is constant in four-second windows. The scaler and SVM are fitted only on healthy flexion windows from the 12 training participants. The 16-configuration search used a validation-only objective with 75% weight on healthy acceptance and 25% on mean rejection across the other-exercise and background groups. Four expansion-cohort participants were reserved for test, disjoint from training, validation and the original pilot. The selected `nu=0.01` and `gamma=0.01` match the pilot settings, so the same-split baseline is identical.

| Split | Accepted / total | Acceptance | Rejection |
| --- | ---: | ---: | ---: |
| Healthy flexion, train | 217 / 219 | 99.09% | 0.91% |
| Healthy flexion, validation | 82 / 109 | 75.23% | 24.77% |
| Healthy flexion, test | 66 / 71 | 92.96% | 7.04% |
| Other exercises, test | 108 / 388 | 27.84% | 72.16% |
| Sampled unstructured background, test | 159 / 641 | 24.80% | 75.20% |

Outlier-ranking AUROC was 0.898 against other exercises and 0.923 against sampled background. Average precision with outliers as the positive class was 0.981 and 0.991, respectively. Outliers greatly outnumber flexion windows in both comparisons, so average precision should be read alongside AUROC and the operating-point rejection rates. Validation participant s9 had 13/38 accepted windows. Test participant s10 had 10/14, compared with 56/57 across the other three test participants. This spread and repeated windows per person limit conclusions about generalization.

## Integration and tests

Replay originates on the backend and sends saved raw six-axis wrist rows through the production window pipeline on a nominal 20 ms schedule. There is no ESP32 dependency. Other recordings and sources keep separate provenance. The catalog exposes original participant, side code and bout identity. Chest metrics and anatomical angle displays are unavailable for wrist-only replay. Saved decision traces contain one timestamped signed score per complete window, and longitudinal score plots group by the artifact fingerprint. Replay progress is filtered by participant, exercise and code and stays out of the hardware activity and baseline summaries.

For live hardware sessions, the optional self-reported pain rating is an integer from 0 to 10. The first compatible live session with shared measurements supplies the baseline for displayed changes. Jerk measures changes in the filtered wrist acceleration, including changes in gravity direction. Paired hardware excursion remains a sensor estimate that depends on mounting, elbow motion and calibration. Replayed wrist counts, live sensor measurements and novelty scores require separate validation for patient use. The current application keeps one monitored capture in a single worker. The history wrist chart stores up to 18,000 points at approximately 5 Hz.

Tests cover replay catalog validation, WebSocket sample delivery, timestamps, persistence, source-specific pain and baseline handling, segmentation and abstention, split disjointness, and offline/exported versus live feature and decision parity on six actual SPARS9x windows. A Chrome smoke test replayed the entire s10 bout, displayed its telemetry, saved it and found it in progress and session history.

### Neutral-to-peak-to-neutral candidate audit

```sh
cd backend
../.venv/bin/python -m app.services.flexion.annotation neutral-candidates \
  ../artifacts/flexion-v2/recordings ../artifacts/flexion-v2/neutral-candidates.csv \
  > ../artifacts/flexion-v2/neutral-candidates.json
```

The audit exports start, peak and return times and wrist gravity-direction angles for independent review. It uses the existing detector's quiet first half-second, 40° peak and 15° return thresholds, and gyroscope motion check. The current 40 flexion bouts yield 67 candidates and 18 within-bout groups of three from seven participants. The thresholds select candidates for review. The initial wrist direction does not establish anatomical neutral, and dynamic acceleration, wrist rotation and torso motion can change the proxy.

A three-rep model requires independently confirmed cycle labels and a shared feature contract between the reference and live measurements. SPARS9x has no synchronized chest orientation, and the live chest-relative angle is a different measurement from this proxy. The three-rep review remains descriptive. Saved session reference graphs use actual window-model scores when present.

### Experimental three-candidate reference model

After running the candidate audit above:

```sh
# From backend/
../.venv/bin/python -m app.services.flexion.rep_study \
  ../artifacts/flexion-v2/neutral-candidates.csv ../artifacts/flexion-reps
```

This fits a StandardScaler and RBF One-Class SVM on median wrist-proxy peak excursion and the range of peak excursions within each group. Neither feature includes rep duration. Groups are disjoint within a recording, and leave-one-participant-out evaluation fits the scaler and SVM anew in each fold. Hyperparameters are fixed for this exploratory run. The final artifact fits all eligible groups and is separate from the deployed window reference.

The 20-participant audit yields 18 candidate groups across seven participants, with nine groups coming from s0. Held-out acceptance is 6/18 (33.3%), or 57.1% when each participant's acceptance rate has equal weight. The experiment has no verified neutral labels or labeled outlier groups. Its wrist gravity-direction features require a matching live feature pipeline and physical validation before deployment.

### All-exercise three-cycle study

```sh
cd backend
../.venv/bin/python -m app.services.flexion.exercise_rep_study ../dataset ../artifacts/exercise-reps
```

The study reads the raw participant CSVs and considers exercise labels 1–10. It excludes unlabeled background (0). For each contiguous participant, shoulder-side and activity segment, it estimates a cycle period from wrist signals, projects gyroscope readings onto the dominant axis, and integrates the projected velocity. A cycle candidate starts at a low displacement landmark, reaches an interior peak, and returns near the starting displacement. The algorithm breaks a sequence wherever a cycle fails its period, excursion or return check. Groups contain three consecutive candidates and do not overlap within a sequence.

Each label has its own scaler and One-Class SVM. The model uses median peak excursion and variation in peak excursion across the three candidates. Leave-one-participant-out folds evaluate acceptance of held-out same-exercise candidates. These rates do not measure outlier-detection accuracy. The starting phase is inferred from wrist signals, and independently observed anatomical neutral and cycle counts are unavailable. Model artifacts and per-group held-out scores are saved under each label. These exploratory models require a validated live feature pipeline before deployment.

### Live and saved three-rep reference

```sh
cd backend
../.venv/bin/python -m app.services.flexion.exercise_rep_study ../dataset ../artifacts/live-exercise-reps --sparse
```

The sparse study uses actual wrist gyroscope samples spaced 0.6 s apart within each training candidate, approximating the observed ESP32 stream. Both training and live scoring use the same timestamp-aware projected-gyroscope excursion calculation and two group features. The training study simulates occasional missed packets and reports held-out results in the generated summary. The reference loader defaults to `artifacts/live-exercise-reps` and also supports `LIVE_REP_MODELS`.

Live ESP32 groups close at reps 3, 6, 9, and so on. A rep needs at least four valid wrist samples and samples covering the detected start and return. A gap above 0.85 s is accepted only when it is at most 1.25 s and covers at most 30% of the sampled rep. Missing groups have no score. After Finish & Save, open the session in Session History to view the group scores and zero decision boundary. The current live exercise mapping covers forward flexion. Other protocols require confirmed exercise mappings. Dataset boundaries are wrist-derived candidates, whereas live boundaries come from paired orientation and still need independent validation.
