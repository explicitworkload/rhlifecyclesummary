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


def clean_date_str(val):
    """Sanitize date strings by stripping full ISO timestamps and 'N/A' artifacts."""
    if not val or not isinstance(val, str):
        return None
    val = val.strip()
    if val.upper() in ["N/A", "NONE", "NULL", ""]:
        return None
    # Preserve words like "Ongoing"
    if val.lower() == "ongoing":
        return "Ongoing"
    # Strip full ISO timestamps down to YYYY-MM-DD
    if len(val) >= 10 and val[4] == "-" and val[7] == "-":
        return val[:10]
    return val

def extract_dates(phase_data):
    """Extracts start and end date tuple string for status and days remaining calculations."""
    if not phase_data or isinstance(phase_data, str):
        return None, None
    s = phase_data.get("start_date")
    e = phase_data.get("end_date") or phase_data.get("date")

    return clean_date_str(s), clean_date_str(e)


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
    """Formats phase objects into clean strings while preserving text descriptions and removing N/A prefixes."""
    if not phase_data:
        return "N/A"
    
    if isinstance(phase_data, str):
        text = phase_data.replace("N/A to ", "").replace("N/A - ", "").strip()
        cleaned = clean_date_str(text)
        return cleaned if cleaned else ("N/A" if text.upper() == "N/A" else text)

    if isinstance(phase_data, dict):
        # 1. Preserve explicit text descriptions if provided by the Red Hat API
        raw_text = phase_data.get("date_description") or phase_data.get("description") or phase_data.get("text")
        if raw_text and isinstance(raw_text, str):
            cleaned_raw = raw_text.replace("N/A to ", "").replace("N/A - ", "").strip()
            if cleaned_raw and cleaned_raw.upper() != "N/A":
                if len(cleaned_raw) >= 10 and cleaned_raw[4] == "-" and cleaned_raw[7] == "-":
                    return clean_date_str(cleaned_raw)
                return cleaned_raw

        # 2. Extract and sanitize start and end values
        start_val = clean_date_str(phase_data.get("start_date_description") or phase_data.get("start_date"))
        end_val = clean_date_str(phase_data.get("end_date_description") or phase_data.get("end_date") or phase_data.get("date"))

        # Only display range if BOTH valid start and end dates exist and differ
        if start_val and end_val and start_val != end_val:
            return f"{start_val} to {end_val}"
        elif end_val:
            return str(end_val)
        elif start_val:
            return str(start_val)

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
                # Specific RHEL Phase Matches
                elif "extended life cycle support" in p_name or "els) add-on" in p_name:
                    phases_map["elc"] = phase
                    phases_map["els1"] = phase
                    phases_map["els"] = phase
                elif "extended life phase" in p_name:
                    phases_map["long_life"] = phase
                # EUS & ELS Term Matches
                elif "els term 3" in p_name or "els 3" in p_name or "els (3)" in p_name:
                    phases_map["els3"] = phase
                elif "extended update support term 3" in p_name or "eus term 3" in p_name:
                    phases_map["eus3"] = phase
                elif "els term 2" in p_name or "els 2" in p_name or "els (2)" in p_name or "els phase 2" in p_name:
                    phases_map["els2"] = phase
                elif "extended update support term 2" in p_name or "eus term 2" in p_name:
                    phases_map["eus2"] = phase
                elif "extended update support" in p_name or "eus term 1" in p_name or "eus" in p_name:
                    if not phases_map["eus1"]:
                        phases_map["eus1"] = phase
                elif "els 1" in p_name or "els (1)" in p_name or "els phase 1" in p_name:
                    phases_map["els1"] = phase
                    if not phases_map["els"]:
                        phases_map["els"] = phase
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

        # Sort versions from newest to oldest by GA date
        def get_sort_key(v):
            ga_str = v.get("ga") or ""
            if len(ga_str) >= 10 and ga_str[0].isdigit():
                return ga_str[:10]
            ver_clean = "".join([c for c in v.get("name", "") if c.isdigit() or c == "."])
            return ver_clean

        parsed_versions.sort(key=get_sort_key, reverse=True)

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
    # Tell Cloudflare Edge to cache this API response for 12 hours (43200 seconds)
    response.headers["Cache-Control"] = "public, max-age=3600, s-maxage=43200"
    
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