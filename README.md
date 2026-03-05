# VICSTA Hackathon – Grand Finale
**VIT College, Kondhwa Campus | 5th – 6th March**

---

## Team Details

**- Team Name: Tech Tonic **
- **Members:**
- Tanvi Nanaware
- Swanand Kalekar
- Omkar Sonawane
- Samruddhi Walunjkar
- **Domain:** Productivity and Security (PS-01)

---

## Project

**Problem:**

Traditional CCTV surveillance systems rely on simple motion detection, which often triggers a large number of false alarms caused by shadows, animals, or environmental changes. This leads to alarm fatigue for security personnel and reduces the effectiveness of monitoring. There is a need for an intelligent surveillance system that can accurately detect human presence and analyze behavior to identify suspicious activities such as loitering or rapid movement while filtering out false alerts. 

**Solution: ** 

Fusion Eye is a lightweight AI-powered surveillance system designed to transform traditional CCTV cameras into intelligent security monitoring tools. The system detects human presence and analyzes behavioral patterns in real time to identify suspicious activities while reducing false alarms caused by shadows, animals, or environmental motion.
The system processes live video input from a camera and applies a multi-stage analysis pipeline to detect potential threats.

🎥 1. Video Capture
The system captures live video frames from a webcam or CCTV feed. These frames are continuously processed to monitor activities in real time.

🧠 2. Object Detection
A pretrained YOLO (You Only Look Once) model is used to detect humans in video frames.
The model identifies bounding boxes around detected persons and filters out irrelevant objects.

⚡ 3. False Positive Filtering
To reduce incorrect alerts caused by shadows or environmental effects, the system performs additional computer vision analysis using:

•	Edge Density Analysis
•	HSV Color Analysis
•	Texture Preservation Checks
These checks help distinguish real human objects from shadows, animals, or lighting changes.

👤 4. Human Verification
The detected objects are further verified using visual characteristics such as:
•	Body proportion
•	Shape analysis
• Surface texture
This step ensures the detected object is actually a human.

🏃 5. Behavior Analysis
Once a human is confirmed, the system analyzes movement patterns and duration of presence to detect suspicious behaviors such as:

•	 Loitering – when a person remains in the same area for an extended period
•	 Running or sudden movement – indicating potential abnormal activity

💡 6. Explainable Alerts
When suspicious behavior is detected, the system generates an alert along with a clear explanation describing why the alert was triggered.
Example:
⚠️ Loitering Detected
Person present in frame for more than 10 seconds

📊 7. Output Dashboard
The final output is displayed on a monitoring dashboard that includes:

•	 Live video feed
•	 Alert notifications
•	Event logs and snapshots
This helps security personnel quickly understand and respond to potential threats.

---

## Rules to Remember

- All development must happen **during** the hackathon only
- Push code **regularly** — commit history is monitored
- Use only open-source libraries with compatible licenses and **credit them**
- Only **one submission** per team
- All members must be present **both days**

---

## Attribution

List any external libraries, APIs, or datasets used here.

---

> *"The world is not enough — but it is such a perfect place to start."* — James Bond
>
> All the best to every team. Build something great. 🚀
