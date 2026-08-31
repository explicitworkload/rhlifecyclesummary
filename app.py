import asyncio
from datetime import datetime
import json
import logging
import os
import re

from typing import Optional
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
import httpx
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from azure_token_refresh import AZURE_CONFIGURED, get_token as azure_get_token, get_chat_url as azure_get_chat_url, start_background_refresh as azure_start_refresh

# 1. Initialize App & Logger
app = FastAPI(title="Red Hat Product Life Cycle Dashboard")
templates = Jinja2Templates(directory="templates")

azure_start_refresh()

# Custom application logger
logger = logging.getLogger("custom_access")
logger.setLevel(logging.INFO)

# Outputs to stdout if no handlers exist
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s: %(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    

PRODUCTS_CONFIG = {
    "Red Hat Enterprise Linux": {
        "link": "https://access.redhat.com/support/policy/updates/errata"
    },
    "Red Hat Enterprise Linux AI": {
        "link": "https://access.redhat.com/support/policy/updates/rhelai"
    },
    "Red Hat OpenShift Container Platform": {
        "link": "https://access.redhat.com/support/policy/updates/openshift"
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
    "Red Hat OpenStack Services on OpenShift": {
        "link": "https://access.redhat.com/support/policy/updates/openstack/platform"
    },
}

API_URL = "https://access.redhat.com/product-life-cycles/api/v1/products"

class RealIPLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Safely parse X-Forwarded-For only if it exists
        xff = request.headers.get("X-Forwarded-For")
        first_xff = xff.split(",")[0].strip() if xff else None

        real_ip = (
            request.headers.get("X-Visitor-IP")
            or request.headers.get("X-Real-IP")
            or request.headers.get("CF-Connecting-IP")
            or first_xff
            or (request.client.host if request.client else "127.0.0.1")
        )

        response = await call_next(request)

        # Skip logging internal health checks to keep console output clean
        if request.url.path != "/health":
            logger.info(
                f'{real_ip} - "{request.method} {request.url.path} HTTP/{request.scope.get("http_version", "1.1")}" {response.status_code}'
            )
        return response

app.add_middleware(RealIPLoggingMiddleware)


def clean_date_str(val):
    """Sanitize date strings by stripping ISO timestamps, 'N/A' artifacts, and foreign localized strings."""
    if not val or not isinstance(val, str):
        return None
    val = val.strip()

    # Filter out English & Japanese N/A variants
    na_variations = ["N/A", "NONE", "NULL", "", "該当なし", "該当無し"]
    if val.upper() in na_variations or val in na_variations:
        return None

    if val.lower() == "ongoing":
        return "Ongoing"
    if len(val) >= 10 and val[4] == "-" and val[7] == "-":
        return val[:10]
    return val


def format_phase_date(phase_data):
    """Formats phase objects into clean strings while removing foreign N/A prefixes."""
    if not phase_data:
        return "N/A"

    if isinstance(phase_data, str):
        text = (
            phase_data.replace("N/A to ", "")
            .replace("N/A - ", "")
            .replace("該当なし", "")
            .strip()
        )
        cleaned = clean_date_str(text)
        return cleaned if cleaned else ("N/A" if (text.upper() == "N/A" or not text) else text)

    if isinstance(phase_data, dict):
        raw_text = phase_data.get("date_description") or phase_data.get("description") or phase_data.get("text")
        if raw_text and isinstance(raw_text, str):
            cleaned_raw = (
                raw_text.replace("N/A to ", "")
                .replace("N/A - ", "")
                .replace("該当なし", "")
                .strip()
            )
            if cleaned_raw and cleaned_raw.upper() != "N/A":
                if len(cleaned_raw) >= 10 and cleaned_raw[4] == "-" and cleaned_raw[7] == "-":
                    return clean_date_str(cleaned_raw)
                return cleaned_raw

        start_val = clean_date_str(phase_data.get("start_date_description") or phase_data.get("start_date"))
        end_val = clean_date_str(phase_data.get("end_date_description") or phase_data.get("end_date") or phase_data.get("date"))

        if start_val and end_val and start_val != end_val:
            return f"{start_val} to {end_val}"
        elif end_val:
            return str(end_val)
        elif start_val:
            return str(start_val)

    return "N/A"

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


async def fetch_product_data(client: httpx.AsyncClient, product_name: str, config: dict):
    try:
        response = await client.get(API_URL, params={"name": product_name})
        if response.status_code != 200:
            return None

        data = response.json().get("data", [])
        if not data:
            return None

        product_info = data[0]
        official_link = config.get("link") or product_info.get("link", "#")

        # 1. Group version objects by unique version name
        grouped_versions = {}

        for ver in product_info.get("versions", []):
            ver_name = ver.get("name", "N/A")
            if ver_name not in grouped_versions:
                grouped_versions[ver_name] = {
                    "name": ver_name,
                    "type": ver.get("type", "N/A"),
                    "tier": ver.get("tier") or "N/A",
                    "ocp_compat": ver.get("openshift_compatibility") or "N/A",
                    "ocp_aligned": ver.get("openshift_aligned_version") or ver.get("extra_header_value") or "N/A",
                    "final_minor": ver.get("final_minor_release") or ver.get("last_minor_release") or "N/A",
                    "raw_phases": []
                }
            
            # Accumulate all phases for this version name
            grouped_versions[ver_name]["raw_phases"].extend(ver.get("phases", []))

        parsed_versions = []

        # 2. Parse accumulated phases per version
        for ver_name, ver in grouped_versions.items():
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

            for phase in ver["raw_phases"]:
                p_name = phase.get("name", "").lower()

                # Base Support Phases
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

                # --- Strict Term 3 Matches (Evaluated BEFORE general checks) ---
                elif "term 3" in p_name or "3" in p_name:
                    if "els" in p_name or "extended life" in p_name:
                        phases_map["els3"] = phase
                    elif "eus" in p_name or "extended update" in p_name:
                        phases_map["eus3"] = phase

                # --- Strict Term 2 Matches (Evaluated BEFORE general checks) ---
                elif "term 2" in p_name or "2" in p_name:
                    if "els" in p_name or "extended life" in p_name:
                        phases_map["els2"] = phase
                    elif "eus" in p_name or "extended update" in p_name:
                        phases_map["eus2"] = phase

                # --- Term 1 / Generic EUS & ELS Matches ---
                elif "term 1" in p_name or "1" in p_name:
                    if "els" in p_name or "extended life" in p_name:
                        phases_map["els1"] = phase
                        if not phases_map["els"]:
                            phases_map["els"] = phase
                    elif "eus" in p_name or "extended update" in p_name:
                        if not phases_map["eus1"]:
                            phases_map["eus1"] = phase

                # --- Fallbacks ---
                elif "extended update support" in p_name or p_name == "eus":
                    if not phases_map["eus1"]:
                        phases_map["eus1"] = phase
                elif "extended life cycle support" in p_name or "extended life support" in p_name or "els" in p_name:
                    phases_map["elc"] = phase
                    if not phases_map["els"]:
                        phases_map["els"] = phase
                    if not phases_map["els1"]:
                        phases_map["els1"] = phase
                elif "extended life phase" in p_name or "long-life" in p_name or "long life" in p_name:
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
                    "name": ver["name"],
                    "type": ver["type"],
                    "tier": ver["tier"],
                    "ocp_compat": ver["ocp_compat"],
                    "ocp_aligned": ver["ocp_aligned"],
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
                    "final_minor": ver["final_minor"],
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
async def get_lifecycle_data(t: Optional[str] = None):
    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks = [
            fetch_product_data(client, prod_name, config)
            for prod_name, config in PRODUCTS_CONFIG.items()
        ]
        results = await asyncio.gather(*tasks)

    valid_results = [r for r in results if r is not None]
    payload = {"products": valid_results}
    
    # Set default cache headers
    response_headers = {
        "Cache-Control": "public, max-age=3600, s-maxage=43200"
    }

    if t is not None:
        response_headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

    return JSONResponse(content=payload, headers=response_headers)

@app.get("/robots.txt", response_class=PlainTextResponse)
def get_robots():
    return "User-agent: *\nAllow: /"

@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    response = templates.TemplateResponse(request=request, name="index.html")
    response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


# --- Lifecycle Advisor Chatbot (Groq) ---

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-safeguard-20b")
GROQ_API_URL = os.environ.get("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")

LIFECYCLE_SYSTEM_PROMPT = """\
You are the Red Hat Lifecycle Advisor. Today: {today}
You ONLY answer questions about Red Hat product lifecycles, support phases, EOL dates, version compatibility, and upgrade planning. If a user asks about anything else (configuration, troubleshooting, installation, general IT advice), politely decline and redirect them to the appropriate Red Hat documentation or support channels. Do not provide step-by-step guides, tutorials, or advice outside of lifecycle topics.
Only use tools when the user asks about a specific product lifecycle, support dates, or EOL status. For greetings or general questions, reply directly without tools.
Use `lookup_lifecycle` for a specific product/version, `list_products` to find product names. Never guess dates.
When recommending a version: compare each version's Full Support End date against today ({today}). A version is in Full Support ONLY if its Full Support End date is IN THE FUTURE (after {today}). Recommend the latest version whose Full Support End is after today. NEVER recommend a version whose Full Support has already ended — even if it still has Maintenance or EUS remaining, it is too old for a new deployment.
For cross-product compatibility questions (e.g. which OpenShift version supports which AAP version), answer to the best of your knowledge based on official Red Hat documentation. If you are not confident, clearly state that the user should verify against the official Red Hat compatibility matrix or the product's release notes.
OpenShift operators (e.g. OpenShift Virtualization, OpenShift Serverless, OpenShift Service Mesh, OpenShift Logging, etc.) follow the lifecycle of the OpenShift Container Platform version they are installed on — they do NOT have independent lifecycles. If asked about an operator's EOL, look up the corresponding OpenShift Container Platform version instead. Do NOT fabricate separate lifecycle data for operators. When reporting "support remaining", base it on the last Maintenance Support phase end date — some products like AAP have multiple maintenance phases (Maintenance 1, Maintenance 2); use the final one as the included support end. EUS (Extended Update Support) is a separately purchased add-on and must always be flagged as such (e.g. "EUS is available as a paid add-on until YYYY-MM-DD"). Never combine Maintenance + EUS into a single "total support" figure without clearly noting EUS requires a separate subscription.
Always include the specific version number in tables and recommendations (e.g. "AAP 2.7", "Quay 3.18", "Keycloak 26.6").
When users ask about notifications, reminders, or alerts for EOL/support dates, always first recommend using the calendar export feature built into this dashboard — each product version row has a calendar icon that downloads an .ics file with reminder alerts at 120, 90, 60, and 30 days before expiry. Suggest this as the primary option before mentioning any other methods.
State dates concretely. Flag EOL products for immediate upgrade. Flag products within 12 months of EOL as urgent.
If a user asks about adding new products to the dashboard, direct them to open an issue or contribute at https://github.com/explicitworkload/rhlifecyclesummary.
Never mention internal tool names (lookup_lifecycle, list_products) to users. These are your internal tools — users cannot see or use them. Instead of saying "use the lookup_lifecycle tool", just look up the data yourself and present the answer.
Keep answers concise with markdown formatting.
"""

LIFECYCLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_lifecycle",
            "description": "Look up lifecycle phases and support dates for a specific Red Hat product and version from the official Red Hat Product Life Cycles API. Returns phase dates (GA, Full Support, Maintenance, EUS, ELS, EOL), current status, and compatibility info.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "The exact Red Hat product name. Must match one of: 'Red Hat Enterprise Linux', 'Red Hat Enterprise Linux AI', 'Red Hat OpenShift Container Platform', 'Red Hat OpenShift AI Self-Managed', 'Red Hat Ansible Automation Platform', 'Red Hat Quay', 'Red Hat build of Keycloak', 'Red Hat Single Sign-On', 'Red Hat JBoss Enterprise Application Platform', 'Red Hat Data Grid', 'Red Hat Edge Manager', 'Red Hat build of MicroShift', 'Red Hat OpenStack Platform'. Use list_products if unsure."
                    },
                    "version": {
                        "type": "string",
                        "description": "The version number, e.g. '9', '4.14', '2.5'. Omit to get the latest version."
                    }
                },
                "required": ["product_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_products",
            "description": "List all Red Hat products available in the lifecycle database with their version counts. Use when unsure of the exact product name.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]


async def execute_tool(tool_name: str, arguments: dict) -> str:
    async with httpx.AsyncClient(timeout=15.0) as client:
        if tool_name == "lookup_lifecycle":
            product_name = arguments.get("product_name", "")
            version = arguments.get("version")
            resp = await client.get(API_URL, params={"name": product_name})
            if resp.status_code != 200:
                return json.dumps({"error": f"API returned {resp.status_code}"})
            data = resp.json().get("data", [])
            if not data:
                return json.dumps({"error": f"Product '{product_name}' not found. Use list_products to see available names."})
            product = data[0]
            versions = product.get("versions", [])
            if version:
                matched = [v for v in versions if v.get("name") == version]
                if not matched:
                    available = [v.get("name") for v in versions]
                    return json.dumps({"error": f"Version '{version}' not found", "available_versions": available})
                target = matched[0]
            else:
                target = versions[0] if versions else None
                if not target:
                    return json.dumps({"error": "No versions found for this product"})
            phases = {}
            for phase in target.get("phases", []):
                start = phase.get("start_date", "N/A")
                end = phase.get("end_date") or phase.get("date", "N/A")
                if isinstance(start, str) and "T" in start:
                    start = start[:10]
                if isinstance(end, str) and "T" in end:
                    end = end[:10]
                phases[phase.get("name", "Unknown")] = {"start": start, "end": end}
            result = {
                "product": product.get("name"),
                "version": target.get("name"),
                "current_phase": target.get("type"),
                "tier": target.get("tier", "N/A"),
                "openshift_compatibility": target.get("openshift_compatibility", "N/A"),
                "phases": phases
            }
            return json.dumps(result)

        elif tool_name == "list_products":
            resp = await client.get(API_URL)
            if resp.status_code != 200:
                return json.dumps({"error": f"API returned {resp.status_code}"})
            data = resp.json().get("data", [])
            products = [
                {"name": p.get("name"), "versions_count": len(p.get("versions", []))}
                for p in data
            ]
            return json.dumps({"products": products})

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


class ChatRequest(BaseModel):
    message: str
    history: list = []


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest, request: Request):
    xff = request.headers.get("X-Forwarded-For")
    client_ip = (
        request.headers.get("X-Visitor-IP")
        or request.headers.get("X-Real-IP")
        or request.headers.get("CF-Connecting-IP")
        or (xff.split(",")[0].strip() if xff else None)
        or (request.client.host if request.client else "unknown")
    )

    if not GROQ_API_KEY and not AZURE_CONFIGURED:
        return JSONResponse(
            status_code=503,
            content={"error": "Lifecycle Advisor is not configured. Set AZURE_OPENAI_* or GROQ_API_KEY environment variables."}
        )

    today = datetime.now().strftime("%Y-%m-%d")
    system_prompt = LIFECYCLE_SYSTEM_PROMPT.format(today=today)

    messages = [{"role": "system", "content": system_prompt}]
    for msg in req.history[-6:]:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": req.message})

    log_prefix = f"[chat] {client_ip}"

    async def call_llm(client, payload, step_label=""):
        backends = []
        if AZURE_CONFIGURED:
            try:
                token = azure_get_token()
                backends.append(("azure", azure_get_chat_url(), {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}))
            except Exception as e:
                logger.warning(f"{log_prefix} {step_label} Azure token fetch failed: {e}, skipping Azure")
        if GROQ_API_KEY:
            backends.append(("groq", GROQ_API_URL, {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}))

        for backend_name, url, hdrs in backends:
            for attempt in range(3):
                resp = await client.post(url, headers=hdrs, json=payload)
                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("retry-after", "20"))
                    logger.warning(f"{log_prefix} {step_label} [{backend_name}] rate limited, retrying in {retry_after}s (attempt {attempt+1}/3)")
                    await asyncio.sleep(retry_after)
                    continue
                if resp.status_code == 200:
                    usage = resp.json().get("usage", {})
                    logger.info(f"{log_prefix} {step_label} [{backend_name}] ok — prompt={usage.get('prompt_tokens',0)} completion={usage.get('completion_tokens',0)} total={usage.get('total_tokens',0)}")
                    return resp
                else:
                    logger.error(f"{log_prefix} {step_label} [{backend_name}] error {resp.status_code}: {resp.text[:200]}")
                    break
            logger.warning(f"{log_prefix} {step_label} [{backend_name}] failed, trying next backend")

        return resp

    max_iterations = 12
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            for iteration in range(max_iterations):
                payload = {
                    "model": GROQ_MODEL,
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 1024
                }
                if iteration < max_iterations - 1:
                    payload["tools"] = LIFECYCLE_TOOLS
                else:
                    logger.info(f"{log_prefix} final iteration — forcing answer without tools")
                resp = await call_llm(client, payload, step_label=f"step {iteration+1}/{max_iterations}")
                if resp.status_code != 200:
                    logger.error(f"{log_prefix} LLM returned {resp.status_code}: {resp.text[:300]}")
                    return JSONResponse(status_code=resp.status_code, content={"error": resp.text})

                result = resp.json()
                choice = result.get("choices", [{}])[0]
                msg = choice.get("message", {})
                finish_reason = choice.get("finish_reason")

                if finish_reason == "tool_calls" or msg.get("tool_calls"):
                    messages.append(msg)
                    for tool_call in msg.get("tool_calls", []):
                        fn = tool_call.get("function", {})
                        tool_name = fn.get("name", "")
                        try:
                            arguments = json.loads(fn.get("arguments", "{}"))
                        except json.JSONDecodeError:
                            arguments = {}
                        logger.info(f"{log_prefix} step {iteration+1}/{max_iterations} tool={tool_name} args={arguments}")
                        tool_result = await execute_tool(tool_name, arguments)
                        if len(tool_result) > 2000:
                            tool_result = tool_result[:2000] + '..."}'
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.get("id", ""),
                            "content": tool_result
                        })
                    continue

                return JSONResponse(content={"response": msg.get("content", "")})

        return JSONResponse(content={"response": "I wasn't able to complete the lookup. Please try again."})
    except Exception as e:
        logger.error(f"{log_prefix} chat error: {type(e).__name__}: {e}")
        return JSONResponse(status_code=500, content={"error": f"Internal error: {type(e).__name__}: {str(e)}"})