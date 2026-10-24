# Campus Chakra Demo Video Script (Strict 2 Minutes 30 Seconds)
**Event:** Srujana 2026 | Prompt to Product  
**Target Time:** 02:25 (Buffer: 5 seconds)  

---

### [00:00 – 00:30] Product Overview & Campus Problem Statement
- **Screen:** Show the Campus Chakra navigation and Chanakya University Global Campus headline. Hover over the 5 KPI cards (Electricity, Solar, Water, Circular Diversion, Net Carbon).
- **Voiceover / Narration:**
  > *"Welcome to Campus Chakra — our AI-driven Predictive Circular-Resource Grid engineered for Chanakya University's multi-building Global Campus in Bengaluru. Managing heterogeneous resources across academic blocks, residential hostels, dining halls, and labs is conventionally crippled by lagging manual audits, unforecasted demand surges, and noisy IoT data. Campus Chakra transforms raw campus telemetry into an intelligent, autonomous circular micro-grid operating under strict edge hardware constraints."*

---

### [00:30 – 01:05] Live Edge Smart-Bin Classification & Sub-Millisecond Latency
- **Screen:** Switch to **"Edge Smart-Bin"** tab. Click **"▶ Start Live Bin Feed"**. Watch the hero card update dynamically with sensor gauges, material classifications, confidence scores, and autonomous circular destination routing. Highlight the confusion matrix.
- **Voiceover / Narration:**
  > *"Here on the Edge Smart-Bin tab, our system fuses five noisy physical sensors: load cell mass, dielectric moisture, inductive metal signals, optical transparency, and piezo vibration. Meeting the competition target of >85% accuracy and <2 seconds latency, our ensemble reaches 86.4% cross-validated accuracy across 6 waste categories. More importantly, we exported a compact 40-tree micro-forest that runs directly on low-power edge microcontrollers in just 0.18 milliseconds — over 10,000 times faster than the edge requirement — routing organics to the campus composter and dry recyclables to certified off-takers."*

---

### [01:05 – 01:35] Short-Horizon 6h/12h Forecasting & Edge Trade-Off Justification
- **Screen:** Switch to **"6h/12h Demand Forecast"** tab. Select **Boys Hostel (B05)**, switch between Electricity and Water. Point out the dashed green proactive forecast line and the spike alert cards.
- **Voiceover / Narration:**
  > *"Campus Chakra goes beyond passive monitoring to proactive 6-hour and 12-hour ahead demand forecasting. By training lightweight gradient-boosted trees with calendar events and weather drivers, we achieved 14.2% error and 0.89 spike detection F1. Compared to a naive baseline, this model requires only 18 microseconds of compute and 120 kilobytes of memory, allowing a single low-cost Raspberry Pi Zero edge gateway to predict demand surges across the entire campus in under two milliseconds."*

---

### [01:35 – 02:05] Root-Cause Attribution & Offline Data Integrity Reconciler
- **Screen:** Switch to **"Root-Cause & Actions"** tab to show the Girls Hostel pipe leak and Food Court alumni surge. Then switch to **"Data Integrity & Sync"** tab, click **"Cut Network Uplink"**, show local buffer queue incrementing, then click **"Restore & Flush Buffer"** and watch the idempotent sync logs.
- **Voiceover / Narration:**
  > *"Unlike raw dashboards, Campus Chakra attributes anomalies to specific causes. It achieved 100% independent recall against all 13 ground-truth facility incidents recorded by staff, identifying the Girls Hostel underground leak and calculating exact savings in rupees and carbon. To ensure operational integrity when campus networks fail, our edge gateways buffer telemetry locally and merge back into the central grid using idempotent sequencing keys without ever corrupting campus aggregates."*

---

### [02:05 – 02:30] Occupant Incentive Loop & AI Engineering Closing
- **Screen:** Switch to **"Eco-Credits Leaderboard"** tab, show weekly building rankings and badges. Briefly open the **"Multi-Agent Copilot"** modal, showing the Nemotron-Llama-Gemini reasoning trace.
- **Voiceover / Narration:**
  > *"Finally, our closed-loop Eco-Credits leaderboard normalizes consumption against each building's own baseline, driving an 18.4% reduction in peak consumption across student hostels. Designed for a hardware BOM under ₹14,200 per building and scaling seamlessly to 30+ buildings, Campus Chakra proves how modern AI and edge computing create a sustainable, resilient campus. Thank you!"*
