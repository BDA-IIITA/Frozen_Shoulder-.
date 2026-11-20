# ShoulderSense System Architecture

## 1. Overview & Biomechanical Design

**ShoulderSense** is a clinical-grade wearable monitoring and rehabilitation platform for patients recovering from frozen shoulder (*adhesive capsulitis*).

The system continuously acquires orientation data from dual BNO086 9-axis Inertial Measurement Units (IMUs):
- **Sensor 1 (Torso / Chest):** Acts as the anatomical reference frame, tracking posture and torso sway.
- **Sensor 2 (Upper Arm):** Mounted on the lateral aspect of the humerus, tracking arm elevation and rotation.

```
                      +-----------------------------+
                      |   Torso IMU (BNO086 #1)     |
                      |   Upper Arm IMU (BNO086 #2) |
                      +--------------+--------------+
                                     | I2C (0x4A, 0x4B)
                      +--------------v--------------+
                      |  ESP32-WROOM-32 Wearable Hub|
                      +--------------+--------------+
                                     | HTTP POST / WebSocket
                                     v
                      +-----------------------------+
                      |     FastAPI Backend API     |
                      +--------------+--------------+
                                     |
    +--------------------------------+--------------------------------+
    |                                |                                |
    v                                v                                v
+------------------+     +-------------------+              +-------------------+
| Biomechanics &   |     | SQLite / Postgres |              | Live WebSocket    |
| Relative Quat FSM|     | Persistent DB     |              | Broadcasting      |
+------------------+     +-------------------+              +---------+---------+
                                                                      |
                                                                      v
                                                            +-------------------+
                                                            | React + Vite + TS |
                                                            | Clinical Frontend |
                                                            +-------------------+
```

---

## 2. Quaternion Mathematics & Coordinate Frames

### Relative Orientation Calculation
Let $q_{chest} = [x_c, y_c, z_c, w_c]$ and $q_{arm} = [x_a, y_a, z_a, w_a]$ be the unit quaternions representing orientation in world coordinates.

The relative rotation $q_{rel}$ of the upper arm relative to the torso frame is computed using the Hamiltonian conjugate:
$$q_{rel} = q_{chest}^* \otimes q_{arm}$$
where $q_{chest}^* = [-x_c, -y_c, -z_c, w_c]$.

### Neutral Calibration Offset
When the user captures a neutral baseline, $q_{neutral}$ is stored. For subsequent samples:
$$q_{effective} = q_{neutral}^* \otimes q_{rel}$$

### Anatomical Angle Extraction
From $q_{effective} = [x, y, z, w]$:
- **Pitch (Flexion):** Forward sagittal elevation ($\approx 0^\circ$ to $180^\circ$).
- **Roll (Abduction):** Lateral coronal elevation ($\approx 0^\circ$ to $180^\circ$).
- **Yaw (Rotation):** Longitudinal humeral rotation (internal/external).

---

## 3. Finite State Machine (FSM) Repetition Counter

Repetition detection is decoupled from noisy threshold crossings using an exercise-specific state machine with hysteresis:

```
[ REST ] --(angle > threshold_down + 2°)--> [ ASCENT ]
   ^                                             |
   |                                    (angle >= threshold_up & delta < -3°)
   |                                             v
[ COMPLETED_REP ] <--(angle <= threshold_down)-- [ DESCENT ]
```

1. **REST:** Arm resting near baseline.
2. **ASCENT:** Arm elevating past ascending threshold.
3. **DESCENT:** Inflection detected, arm returning under control.
4. **COMPLETED_REP:** Increment rep counter only if duration $\ge 1.0\text{s}$ and peak reached threshold.

---

## 4. Machine Learning Integration Interface

The ML subsystem provides a standardized inference contract:
- **Input Feature Vector:** `[ROM, Repetitions, Avg_Duration, Duration_Variance, Peak_Variance, Smoothness, Velocity]`
- **Candidate Models:** Random Forest, Support Vector Machine (SVM), XGBoost.
- **Model Classes:** `Normal movement`, `Restricted movement`, `Irregular movement`.
- **Honest Status Reporting:** When no trained cohort model is loaded, the system explicitly returns:
  `"ML movement assessment is not configured yet."`
  A separate rule-based demonstration heuristic is provided for UI testing, explicitly disclaimed as non-diagnostic.
