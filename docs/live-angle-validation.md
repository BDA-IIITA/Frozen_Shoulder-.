# Live chest-relative angle validation

## What can be measured

The chest and wrist BNO086 orientations determine how the wrist sensor rotates relative to the chest. With the elbow held straight, stable sensor mounts, and the wrist held in a consistent position, this is a proxy for arm elevation. The measurements do not independently determine upper-arm orientation, elbow flexion, scapular motion, or anatomical shoulder range of motion. Different shoulder, elbow, and wrist configurations can produce the same wrist orientation. A third IMU on the upper arm, synchronized to the chest, or an independent reference is needed to isolate upper-arm movement under general conditions.

## Quaternion and time audit

The example firmware calls SparkFun's Rotation Vector API and sends I, J, K, real as named JSON fields x, y, z, w. The backend validates finite values and a plausible norm, then normalizes before using Hamilton products. We interpret the fused reports as active, right-handed sensor-to-common-world rotations. The source confirms the component ordering and rotation-vector report type. The shared heading and physical frame interpretation should still be checked on the actual mounted sensors. [CEVA BNO08X data sheet](https://www.ceva-dsp.com/wp-content/uploads/2019/10/BNO080_085-Datasheet.pdf) · [SparkFun report API](https://github.com/sparkfun/SparkFun_BNO08x_Arduino_Library/blob/main/src/SparkFun_BNO08x_Arduino_Library.cpp) · [Quaternion field conventions](https://github.com/sparkfun/SparkFun_BNO08x_Arduino_Library/blob/main/src/sh2_SensorValue.h)

Let C and W be the chest and wrist rotations. R = inv(C) × W maps wrist coordinates into the chest frame. D = R × inv(R_neutral) describes the change in that frame and cancels a constant right-hand wrist mounting rotation. Left-multiplying by the neutral inverse would express the change in a different frame. Under a common world rotation G, inv(G × C) × (G × W) = R.

Shared setup uses the axis of the neutral-to-forward rotation and the axis of the neutral-to-side rotation. It rejects insufficient motion and nearly parallel captures and fits their directions symmetrically to an orthonormal torso basis. The selected shoulder sets the sign of the outward side reference. The basis is held in memory per device, limb stream and shoulder. Forward flexion and abduction can share it. Resetting neutral clears the directions for that sensor pair. Calibration changes are disabled during recording.

D rotates the calibrated neutral down vector. In torso coordinates (forward x, lateral y, up z), the unsigned sagittal and frontal projections use atan2(|x|, −z) and atan2(|y|, −z) respectively. The perpendicular pure-plane case is separated to avoid a spurious second-plane angle. The azimuth distinguishes forward, side, and mixed movement. The 25° mixed-motion classification is a descriptive cutoff for repetition gating, not an angle adjustment or clinical limit. Exact overhead does not identify a plane. Wrist twist uses the quaternion projection around the neutral long axis and remains a wrist-twist proxy. Speed is the finite difference of the selected estimate in degrees per second.

A world-gravity inclination can describe elevation relative to vertical under the same straight-elbow assumption, but it changes when the torso leans. We use the torso frame to measure the exercise plane under torso motion. Neutral alone zeroes the starting pose, while the two separate reference motions identify the torso directions without assuming how the chest sensor was mounted or that the initial world gravity axis is the desired anatomical axis.

The example firmware caches the two readings independently and puts only transmit time in a packet. Arrival age is available; synchronization and individual sample age cannot be inferred from it. The backend accepts optional per-sensor `sample_timestamp` fields on the same device clock. It displays unknown synchronization for the existing payload, and flags pairs with over 30 ms skew or a sample over 100 ms old when both timestamps are supplied. No firmware changes were made. A stationary pose check can proceed with the current payload, but timing-induced error during movement remains unverified.

## Numerical findings

| Constructed test case | Previous weighted elevation | Current plane projection |
| --- | ---: | ---: |
| Pure 90° forward raise | 90.0° | 90.0° |
| Pure 120° forward raise | 120.0° | 120.0° |
| Horizontal limb, 30° toward the side from forward | 77.9° | 90.0° in forward projection, flagged as mixed |
| True upper arm horizontal, wrist segment pitched down 12° in the same plane | 78.0° | 78.0° wrist estimate |

The earlier Euler-only implementation maps pure 120° pitch to 60°. The immediately preceding vector method avoided that fold but multiplied total elevation by azimuth alignment. At 90° elevation and 30° of off-plane bearing, its output is 90 × cos(30°) = 77.94°. The final example illustrates an observability limit, not a hardware measurement. All constructed examples assume a shared world frame and rigid mounts. Real 90° accuracy and the cause of the user's observed 75–80° reading remain unverified.

## Physical check

1. Confirm **Receiving ESP32 packets** in **Live Monitoring → Live ESP32**, select the shoulder, and keep both sensors mounted in the same positions throughout.
2. Select Forward Flexion or Abduction. Hold the arm-down reference, select **Set neutral**, open **Shared sensor setup**, and capture the two distinct raises in the displayed order. Avoid twisting the wrist or bending the elbow during the test if you can hold the pose comfortably.
3. Before starting a recording, open **Technical details → Verify against a measured angle**. Measure the actual angle independently with a goniometer or a camera/reference setup qualified for the relevant plane. Enter the measured angle while holding the pose, then select **Compare pose**. Repeat after switching the exercise from flexion to abduction. The diagnostic table computes absolute errors and mean absolute error for the current exercise and setup. Copy the values before switching exercise or resetting calibration.
4. Record neutral, forward near 45°, forward near 90°, side near 45°, and side near 90°. Use the measured reference instead of the target in the table. Repeat with the same setup and record the packet synchronization status. Compute overall MAE as the sum of the five absolute errors divided by five.

| Static pose | Independent reference | ShoulderSense estimate | Absolute error |
| --- | --- | --- | --- |
| Neutral down | Unmeasured | Unmeasured | — |
| Forward near 45° | Unmeasured | Unmeasured | — |
| Forward near 90° | Unmeasured | Unmeasured | — |
| Side near 45° | Unmeasured | Unmeasured | — |
| Side near 90° | Unmeasured | Unmeasured | — |

Physical mean absolute error is unavailable until measurements are collected.
