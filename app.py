import asyncio
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import httpx

app = FastAPI(title="Red Hat Product Life Cycle Dashboard")
templates = Jinja2Templates(directory="templates")

PRODUCTS_CONFIG = {
    "Red Hat Enterprise Linux": {
        "link": "https://access.redhat.com/support/policy/updates/errata"
    },
    "Red Hat Enterprise Linux AI": {
        "link": "https://access.redhat.com/support/policy/updates/rhelai"
    },
    "Red Hat OpenShift Container Platform": {
        "link": "https://access.redhat.com/support/policy/updates/openshift#fullsupport"
    },
    "Red Hat OpenShift AI Self-Managed": {
        "link": "https://access.redhat.com/support/policy/updates/rhoai-sm/lifecycle"
    },
    "Red Hat Ansible Automation Platform": {
        "link": "https://access.redhat.com/support/policy/updates/ansible-automation-platform"
    },
    "Red Hat Quay": {
        "link": "https://access.redhat.com/support/policy/updates/rhquay"
    },
    "Red Hat build of Keycloak": {
        "link": "https://access.redhat.com/support/policy/updates/red_hat_build_of_keycloak_notes"
    },
    "Red Hat Single Sign-On": {
        "link": "https://access.redhat.com/support/policy/updates/jboss_notes#p_sso"
    },
    "Red Hat JBoss Enterprise Application Platform": {
        "link": "https://access.redhat.com/support/policy/updates/jboss_notes#p_eap"
    },
    "Red Hat Data Grid": {
        "link": "https://access.redhat.com/support/policy/updates/jboss_notes#p_rhdg"
    },
    "Red Hat Edge Manager": {
        "link": "https://access.redhat.com/support/policy/updates/rhem"
    },
    "Red Hat build of MicroShift": {
        "link": "https://access.redhat.com/support/policy/updates/microshift"
    },
    "Red Hat OpenStack Platform": {
        "link": "https://access.redhat.com/support/policy/updates/openstack/platform"
    },
}

API_URL = "https://access.redhat.com/product-life-cycles/api/v1/products"


def extract_dates(phase_data):
    """Extracts start and end date tuple string for comparison."""
    if not phase_data or isinstance(phase_data, str):
        return None, None
    s = phase_data.get("start_date")
    e = phase_data.get("end_date") or phase_data.get("date")

    def clean(val):
        if val and len(val) >= 10 and val[4] == "-" and val[7] == "-":
            return val[:10]
        return None

    return clean(s), clean(e)


def calculate_days_remaining(end_date_str):
    if not end_date_str:
        return None
    try:
        end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
        now = datetime.now()
        delta = (end_dt - now).days
        return delta
    except ValueError:
        return None


def format_phase_date(phase_data):
    if not phase_data:
        return "N/A"
    if isinstance(phase_data, str):
        return phase_data

    start, end = extract_dates(phase_data)
    if start and end and start != end:
        return f"{start} to {end}"
    elif end:
        return end
    elif start:
        return start
    return "N/A"


async def fetch_product_data(client: httpx.AsyncClient, product_name: str, config: dict):
    try:
        response = await client.get(API_URL, params={"name": product_name})
        if response.status_code != 200:
            return None

        data = response.json().get("data", [])
        if not data:
            return None

        product_info = data[0]
        parsed_versions = []
        official_link = config.get("link") or product_info.get("link", "#")

        for ver in product_info.get("versions", []):
            ver_name = ver.get("name", "N/A")
            status_type = ver.get("type", "N/A")
            tier = ver.get("tier") or "N/A"
            ocp_compat = ver.get("openshift_compatibility") or "N/A"
            ocp_aligned = ver.get("openshift_aligned_version") or ver.get("extra_header_value") or "N/A"
            final_minor = ver.get("final_minor_release") or ver.get("last_minor_release") or "N/A"

            phases_map = {
                "ga": None,
                "full": None,
                "third_party": None,
                "maint": None,
                "maint1": None,
                "maint2": None,
                "eus1": None,
                "eus2": None,
                "eus3": None,
                "elc": None,
                "long_life": None,
                "els": None,
                "els1": None,
                "els2": None,
                "els3": None,
                "eol": None,
            }

            for phase in ver.get("phases", []):
                p_name = phase.get("name", "").lower()

                if "general availability" in p_name or p_name == "ga":
                    phases_map["ga"] = phase
                elif "full support" in p_name:
                    phases_map["full"] = phase
                elif "third-party" in p_name or "third party" in p_name:
                    phases_map["third_party"] = phase
                elif "maintenance support 1" in p_name:
                    phases_map["maint1"] = phase
                elif "maintenance support 2" in p_name:
                    phases_map["maint2"] = phase
                elif "maintenance" in p_name:
                    phases_map["maint"] = phase
                elif "term 3" in p_name and ("extended update" in p_name or "els" in p_name):
                    phases_map["eus3"] = phase
                    phases_map["els3"] = phase
                elif "term 2" in p_name and ("extended update" in p_name or "els" in p_name):
                    phases_map["eus2"] = phase
                    phases_map["els2"] = phase
                elif "term 1" in p_name and "extended update" in p_name:
                    phases_map["eus1"] = phase
                elif "extended update support" in p_name and not phases_map["eus1"]:
                    phases_map["eus1"] = phase
                elif "els 1" in p_name or "els (1)" in p_name or "els phase 1" in p_name or ("els" in p_name and "add-on" in p_name):
                    phases_map["els1"] = phase
                    if not phases_map["els"]:
                        phases_map["els"] = phase
                elif "els 2" in p_name or "els (2)" in p_name or "els phase 2" in p_name:
                    phases_map["els2"] = phase
                elif "extended life cycle" in p_name or "elc" in p_name or "els" in p_name:
                    phases_map["elc"] = phase
                    if not phases_map["els"]:
                        phases_map["els"] = phase
                    if not phases_map["els1"]:
                        phases_map["els1"] = phase
                elif "long-life" in p_name or "long life" in p_name:
                    phases_map["long_life"] = phase
                elif "end of life" in p_name or "eol" in p_name:
                    phases_map["eol"] = phase

            # Target active end date for urgency calculation
            target_phase = phases_map["maint2"] or phases_map["maint1"] or phases_map["maint"] or phases_map["full"] or phases_map["eus1"] or phases_map["eol"]
            _, raw_end = extract_dates(target_phase)
            days_remaining = calculate_days_remaining(raw_end)

            # Extract raw phase date ranges for client-side status calculation
            phase_ranges = {}
            for k, p_data in phases_map.items():
                s, e = extract_dates(p_data)
                if s or e:
                    phase_ranges[k] = {"start": s, "end": e}

            parsed_versions.append(
                {
                    "name": ver_name,
                    "type": status_type,
                    "tier": tier,
                    "ocp_compat": ocp_compat,
                    "ocp_aligned": ocp_aligned,
                    "days_remaining": days_remaining,
                    "phase_ranges": phase_ranges,
                    "ga": format_phase_date(phases_map["ga"]),
                    "full": format_phase_date(phases_map["full"]),
                    "third_party": format_phase_date(phases_map["third_party"]),
                    "maint": format_phase_date(phases_map["maint"]),
                    "maint1": format_phase_date(phases_map["maint1"]),
                    "maint2": format_phase_date(phases_map["maint2"]),
                    "eus1": format_phase_date(phases_map["eus1"]),
                    "eus2": format_phase_date(phases_map["eus2"]),
                    "eus3": format_phase_date(phases_map["eus3"]),
                    "elc": format_phase_date(phases_map["elc"]),
                    "long_life": format_phase_date(phases_map["long_life"]),
                    "els": format_phase_date(phases_map["els"]),
                    "els1": format_phase_date(phases_map["els1"]),
                    "els2": format_phase_date(phases_map["els2"]),
                    "els3": format_phase_date(phases_map["els3"]),
                    "eol": format_phase_date(phases_map["eol"]),
                    "final_minor": final_minor,
                }
            )

        return {
            "product_name": product_name,
            "official_link": official_link,
            "versions": parsed_versions,
        }
    except Exception as e:
        print(f"Error fetching {product_name}: {e}")
        return None


@app.get("/api/data")
async def get_lifecycle_data():
    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks = [
            fetch_product_data(client, prod_name, config)
            for prod_name, config in PRODUCTS_CONFIG.items()
        ]
        results = await asyncio.gather(*tasks)

    valid_results = [r for r in results if r is not None]
    return {"products": valid_results}


@app.get("/", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")