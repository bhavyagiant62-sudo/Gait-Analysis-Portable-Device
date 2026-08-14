# Gait-Analysis-Portable-Device
Wireless Wearable Gait Analysis System — A patented prototype using dual IMU sensors, ESP32, and Raspberry Pi for real-time lower-limb motion tracking, knee-angle estimation, gait parameter analysis, and wireless visualization. Designed for affordable, portable rehabilitation and gait assessment.


## Detailed Description — Wireless Wearable Gait Analysis System

The **Wireless Wearable Gait Analysis System** is a portable prototype developed for real-time monitoring and analysis of lower-limb movement during walking. The system combines **two BNO055 IMU sensors, an ESP32 wireless microcontroller, and a Raspberry Pi processing and visualization unit**. The prototype is designed to provide an affordable alternative to laboratory-based gait analysis systems that require expensive cameras and specialized infrastructure.

### 1. System Architecture

The prototype consists of three main sections:

1. **Wearable sensing section** – two BNO055 IMU sensors.
2. **Wireless data acquisition section** – ESP32.
3. **Processing and visualization section** – Raspberry Pi.

The two IMUs are attached to different segments of the lower limb, typically the **thigh and shank**. Their measurements represent the movement and orientation of the respective body segments. The ESP32 collects the sensor information and communicates it wirelessly to the Raspberry Pi.

The Raspberry Pi acts as the main computing platform. It receives the sensor data, performs processing and calculations, and displays the resulting gait information through the developed graphical interface.

---

### 2. IMU Sensor System

The prototype uses **two BNO055 9-axis absolute orientation IMU sensors**. Each sensor integrates:

* 3-axis accelerometer
* 3-axis gyroscope
* 3-axis magnetometer
* On-board orientation processing

The first sensor is mounted on the **thigh**, while the second sensor is mounted on the **shank/calf**.

During walking, the sensors continuously detect changes in orientation and movement of the corresponding body segments. The relative orientation between the thigh and shank can then be used to estimate **knee joint movement**.

This arrangement allows the system to obtain meaningful lower-limb motion information while using only two wearable sensing points.

---

### 3. ESP32 Data Acquisition

The **ESP32** acts as the central wearable controller.

The two BNO055 sensors communicate with the ESP32 using the **I²C communication protocol**. Both sensors can share the same SDA and SCL lines while using different I²C addresses.

The sensor configuration used in the prototype distinguishes the two IMUs using separate addresses:

* **Thigh IMU → 0x28**
* **Shank IMU → 0x29**

The ESP32 initializes both sensors, receives their motion data, organizes the measurements into data packets, and transmits the acquired information wirelessly to the Raspberry Pi.

The use of wireless communication eliminates the need for a long physical cable between the wearable sensing unit and the processing computer, allowing the subject to walk more naturally during testing.

---

### 4. Wireless Communication

After acquiring the IMU measurements, the ESP32 sends the sensor data to the Raspberry Pi through a wireless network.

The transmitted information can include:

* Sensor identification
* Orientation information
* Acceleration data
* Angular velocity
* Timestamp/data sequence information
* Calculated or raw motion values

The Raspberry Pi continuously listens for incoming data and passes the received information to the processing software.

This communication architecture separates the **wearable sensing hardware** from the **computational platform**, allowing the sensing unit to remain compact.

---

### 5. Raspberry Pi Processing Unit

The **Raspberry Pi** functions as the central processing and visualization unit.

The processing sequence can be represented as:

**Wireless Data Reception → Data Buffer → Data Processing → Orientation Analysis → Joint Angle Estimation → Gait Parameter Calculation → Visualization → Data Storage**

The Raspberry Pi receives the incoming sensor data and organizes the measurements for processing.

Preprocessing can include:

* Data validation
* Noise reduction
* Offset correction
* Sensor calibration
* Synchronization of measurements

The processed orientation information from the thigh and shank sensors is then used to determine the relative movement between the two segments.

---

### 6. Knee Joint Angle Estimation

One of the main functions demonstrated by the prototype is estimation of **knee joint movement**.

The thigh-mounted IMU provides the orientation of the thigh segment, while the shank-mounted IMU provides the orientation of the shank segment.

The relative orientation between these two segments is used to estimate the knee angle:

**Knee angle ≈ Relative orientation of shank with respect to thigh**

As the user walks, the knee angle changes continuously. These changes can be plotted against time to observe the movement pattern throughout the gait cycle.

---

### 7. Gait Analysis

The processed motion data can be used to extract gait-related parameters such as:

* Step count
* Cadence
* Stride time
* Gait cycle duration
* Estimated walking speed
* Knee joint angle
* Knee range of motion
* Stance and swing characteristics where the implemented algorithms support them

These parameters provide quantitative information about the user's walking pattern.

For example, changes in knee range of motion or differences in gait timing can be observed across different walking sessions.

---

### 8. Raspberry Pi Graphical User Interface

A major component of the prototype is the **Raspberry Pi-based graphical user interface**.

The interface provides a user-friendly environment for observing the sensor information and calculated gait parameters.

The GUI is intended to display information such as:

* Real-time sensor values
* IMU orientation
* Knee joint angle
* Gait parameters
* Graphical motion data
* Connection/system status
* Session information

The interface allows the operator to observe the patient's movement while the gait assessment is taking place instead of requiring the data to be analyzed only after the experiment.

---

### 9. Data Logging

The Raspberry Pi can record the acquired and processed information during a gait assessment session.

The stored data can subsequently be used for:

* Comparing multiple walking trials
* Monitoring rehabilitation progress
* Studying changes in gait
* Research and development
* Generating further analytical outputs

This provides the basis for longitudinal monitoring where measurements from different sessions can be compared.

---

### 10. Operating Procedure

The prototype operates according to the following sequence:

**Step 1:** The ESP32 and Raspberry Pi are powered on.

**Step 2:** The ESP32 initializes the two BNO055 IMU sensors.

**Step 3:** The sensors undergo initialization/calibration.

**Step 4:** The thigh and shank IMUs continuously measure lower-limb movement.

**Step 5:** The ESP32 collects the sensor measurements through the I²C interface.

**Step 6:** The ESP32 packages the sensor data and transmits it wirelessly.

**Step 7:** The Raspberry Pi receives the transmitted data.

**Step 8:** The Raspberry Pi preprocesses and synchronizes the sensor measurements.

**Step 9:** The relative orientation between the thigh and shank is determined.

**Step 10:** Knee joint movement and selected gait parameters are calculated.

**Step 11:** The calculated information is displayed on the Raspberry Pi GUI.

**Step 12:** The gait data can be recorded for subsequent analysis.

---

### 11. Key Features of the Prototype

| Feature              | Description                         |
| -------------------- | ----------------------------------- |
| **Sensing**          | Two BNO055 IMUs                     |
| **Sensor Placement** | Thigh and shank                     |
| **Microcontroller**  | ESP32                               |
| **Sensor Interface** | I²C                                 |
| **Wireless Link**    | ESP32 to Raspberry Pi               |
| **Processing Unit**  | Raspberry Pi                        |
| **Primary Analysis** | Lower-limb motion and knee movement |
| **Visualization**    | Raspberry Pi graphical interface    |
| **Data Storage**     | Gait/session data                   |
| **System Type**      | Portable wearable system            |

---

### 12. Advantages

The prototype provides several advantages over conventional laboratory-based systems:

* **Portable:** Can be used outside a dedicated gait laboratory.
* **Wireless:** Reduces physical wiring between the wearable unit and processing system.
* **Low-cost:** Uses commercially available embedded hardware.
* **Real-time:** Enables immediate observation of motion and calculated parameters.
* **Compact:** Requires only two wearable sensing units in the current prototype.
* **Modular:** Hardware and software can be expanded later.
* **User-friendly:** The Raspberry Pi interface provides direct visualization.
* **Research-ready:** Recorded motion data can be used for further algorithm development and validation.

---

### 13. Current Prototype Scope

The present prototype specifically demonstrates **two-IMU lower-limb motion analysis using an ESP32 and Raspberry Pi**. It should be distinguished from the planned future version involving additional IMUs, pressure sensors, and EMG sensors.

The current prototype establishes the core technology:

**Wearable Motion Sensing → Wireless Data Acquisition → Raspberry Pi Processing → Knee Motion/Gait Analysis → Real-Time Visualization**

This core architecture provides the foundation for future development into a more comprehensive multi-sensor gait analysis and rehabilitation platform.
