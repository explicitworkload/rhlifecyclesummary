# 🚀 Red Hat Product Lifecycle Dashboard

An interactive, live dashboard that aggregates and tracks end-of-life (EOL), support phase transitions, and active update windows across Red Hat products. Built with FastAPI and vanilla JavaScript, it consumes the official Red Hat Product Life Cycles API to give system administrators, platform engineers, and enterprise architects a unified view of their infrastructure's support status.

🌐 **Live Demo:** [https://rhlifecycle.kubernetes.day](https://rhlifecycle.kubernetes.day)

![lifecycle-dashboard](images/rhlifecycle-dashboard.png)


<!-- Core Stack -->
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952B3?logo=bootstrap&logoColor=white)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?logo=css3&logoColor=white)
![Render](https://img.shields.io/badge/Render-Hosted-46E3B7?logo=render&logoColor=white)
![Cloudflare](https://img.shields.io/badge/Cloudflare-DNS%20%26%20SSL-F38020?logo=cloudflare&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Supported-2496ED?logo=docker&logoColor=white)
![Podman](https://img.shields.io/badge/Podman-Compatible-892CA0?logo=podman&logoColor=white)
![UptimeRobot](https://img.shields.io/badge/UptimeRobot-Monitored-3BD4AE?logo=uptimerobot&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

## 🌟 Features

- **⚡ Real-Time API Data:** Automatically pulls support lifecycle phases directly from Red Hat's public API endpoints.
- **🏷️ Dynamic Status Resolution:** Accurately evaluates live phase windows (Full Support, Extended Update Support, Maintenance Support, End of Maintenance, and End of Life) based on current dates.
- **📅 .ics Calendar Export (With Alarms):** Download calendar events (`.ics`) for active product versions directly into Outlook, Google Calendar, or Apple Calendar. Includes built-in alert triggers for **120, 90, 60, and 30 days** prior to expiration.
- **⏳ EOL Urgency Counters:** Visual badges automatically flag versions nearing support expiration within 120 days.
- **🔍 Quick Filter & Search:** Easily search by product name, major version, or minor version numbers.
- **📱 Responsive UI:** Built with Bootstrap 5 in a dark enterprise theme.

---

## 🛠️ Supported Products

- **Red Hat Enterprise Linux (RHEL)** *(Includes ELC, Long-Life Add-On, and Final Minor Release tracking)*
- **Red Hat Enterprise Linux AI (RHEL AI)**
- **Red Hat build of Keycloak** *(Includes dependency note support)*
- **Red Hat Ansible Automation Platform (AAP)** *(Term 1 & Term 2 EUS resolution)*
- **Red Hat OpenShift Container Platform (OCP)**
- **Red Hat OpenShift AI Self-Managed**
- **Red Hat Quay**
- **Red Hat Single Sign-On**
- **Red Hat JBoss Enterprise Application Platform**
- **Red Hat Data Grid**
- **Red Hat Edge Manager**
- **Red Hat build of MicroShift**
- **Red Hat OpenStack Platform**
- **Red Hat OpenStack on OpenShift**

*Want to add more Red Hat products to this dashboard? Reach out via email or submit a Pull Request!*

---

## 🛠️ Tech Stack

- **Backend:** Python 3.12+, FastAPI, `httpx` (Asynchronous API client), Jinja2
- **Frontend:** Vanilla JS (ES6+), Bootstrap 5, Bootstrap Icons
- **Data Source:** [Red Hat Product Life Cycles API](https://access.redhat.com/product-life-cycles/api/v1/products)
* **Hosting & PaaS:** [Render](https://render.com/) (Web Services)
* **DNS & Security:** [Cloudflare](https://www.cloudflare.com/) (DNS Only / Proxied Mode with SSL/TLS Full Strict)
* **Uptime Monitoring:** UptimeRobot / Cron-Job.org via `/health` endpoint

## 🐳 Quickstart

This repository automatically builds and publishes container images to **Quay.io** whenever updates are pushed to GitHub.

* **Container Image URL:** `quay.io/jgoh/rhlifecyclesummary:latest`

### Running directly from Quay.io

You can pull and run the latest pre-built container image directly without building it locally:

```bash
# Pull and run using Podman
podman run -d -p 8881:8881 --name rh-dashboard quay.io/jgoh/rhlifecyclesummary:latest

# Or using Docker
docker run -d -p 8881:8881 --name rh-dashboard quay.io/jgoh/rhlifecyclesummary:latest
```

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
```

---

### Running with `podman-compose`

1. **Clone the repository:**
   ```bash
   git clone https://github.com/explicitworkload/rhlifecyclesummary.git
   cd rhlifecyclesummary
   ```

2. **Start the service:**
   ```
   podman-compose up -d
   ```

3. **Stop the service:**
    ```
    podman-compose down
    ```

4. **Build the image (Optional):**
    ```
    podman build -t rh-lifecycle-dashboard .
    ```

5. **Quickstart**
    ```
    podman run -d -p 8881:8881 --name rh-dashboard rh-lifecycle-dashboard
    ```

---

## API & Health Endpoints

| Endpoint | Methods | Description |
| :--- | :--- | :--- |
| `/` | `GET`, `HEAD` | Main Lifecycle Dashboard UI |
| `/api/data` | `GET` | Aggregated JSON feed from Red Hat API sources |
| `/health` | `GET`, `HEAD` | Lightweight service ping endpoint returning `{"status": "ok"}` |
| `/robots.txt` | `GET` | Web crawler routing rules |

---

## ⚠️ Disclaimer

Disclaimer: Dates displayed on this dashboard are dynamically fetched for summary tracking. Always reference official  [Red Hat Product Update Policies](https://access.redhat.com/product-life-cycles/update_policies) linked in each product card for definitive support terms.

---

## 👨‍💻 Maintainer

Maintained with by **John**  
📧 **Email:** [me@kubernetes.day](mailto:me@kubernetes.day). Distributed under the MIT License.

Contributions, bug reports, and feature requests are welcome! Feel free to check the issues page or submit a pull request.
