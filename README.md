# 🚀 Red Hat Product Lifecycle Dashboard

An open-source, lightweight containerized web application that aggregates real-time lifecycle support dates across the Red Hat product ecosystem. Built with Python (FastAPI) and a modern dark-mode Bootstrap interface, this tool helps platform engineers, DevOps teams, and SREs stay ahead of End-of-Life (EOL) timelines and Extended Update Support (EUS) windows.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Podman](https://img.shields.io/badge/Podman-Compatible-purple.svg)
![Docker](https://img.shields.io/badge/Docker-Supported-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green.svg)

---

## 🌟 Key Features

* **⚡ Real-Time Lifecycle Tracking:** Queries official feeds directly from the Red Hat Product Life Cycles API.
* **📦 Broad Product Coverage:** Out-of-the-box tracking for RHEL, RHEL AI, OpenShift (OCP), OpenShift AI (RHOAI), Ansible Automation Platform (AAP), Red Hat Quay, Keycloak, Red Hat SSO, JBoss EAP, Data Grid, Edge Manager, and MicroShift.
* **🎨 Visual Status Indicators:** Clear color-coded status badges for active Full Support, Maintenance Support, EUS/ELS terms, and End-of-Life (EOL).
* **🔍 Instant Live Search:** Search across all product names or specific version numbers (e.g., `2.4`, `OpenShift`, `8.6`) in real time.
* **📱 Responsive & Collapsible UI:** Compact accordion-based layout with single-click "Expand All" and "Collapse All" controls.
* **🔒 Enterprise Ready:** Packaged as a rootless containerized app ready for deployment on Podman, Docker, Kubernetes, or Red Hat OpenShift.

---

## 🛠️ Tech Stack

* **Backend:** Python 3.12, FastAPI, `httpx` (async API client)
* **Frontend:** HTML5, Modern Dark CSS, Bootstrap 5.3, Bootstrap Icons
* **Deployment:** Podman / Docker, `podman-compose`

---

## 📁 Repository Structure

```text
.
├── app.py                # FastAPI backend app & API mapping logic
├── Dockerfile            # Multi-stage/rootless container specification
├── podman-compose.yml    # Orchestration file for Podman/Docker Compose
├── templates/
│   └── index.html        # Responsive frontend template with Bootstrap 5
└── README.md             # Project documentation

