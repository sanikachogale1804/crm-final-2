import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import pymysql
from pymysql.cursors import DictCursor

from pydantic import BaseModel
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse
# ✅ REMOVED: Procurement/vendor router imports

from tools.security_audit_table_api import router as security_audit_table_router
from tools.audit_system_info_api import router as audit_system_info_router

app = FastAPI(title="Smart CRM System")

app.include_router(security_audit_table_router)
app.include_router(audit_system_info_router)

@app.get("/checkroute")
async def checkroute():
    return {"status": "OK"}

class LeadApprovalPayload(BaseModel):
    action: str
    comment: Optional[str] = None

# ============ EMAIL CONFIGURATION ============
SMTP_HOST = "smtp.mailngx.com"
SMTP_PORT = 587
SMTP_USER = "info@cogentsecurity.ai"
SMTP_PASS = "Cogent@2025"

def send_email(to_email: str, subject: str, body: str):
    """Send a plain-text email via SMTP."""
    try:
        msg = MIMEMultipart("alternative")   
        msg["From"] = SMTP_USER
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"✅ Email sent to {to_email}")
    except Exception as e:
        print(f"❌ Email sending failed to {to_email}: {str(e)}")


def send_kickoff_emails(lead_id: str, cursor):
    """
    Send KICKOFF approval notification emails to ALL four approver roles
    (oops, finance, admin, scm) at once when a lead moves to KICKOFF status.
    Each role gets a role-specific email.
    """
    APPROVAL_ROLES = ["oops", "finance", "admin", "scm"]

    role_display = {
        "oops": "OOPS",
        "finance": "Finance",
        "admin": "Admin",
        "scm": "SCM",
    }

    approval_sequence_note = "Approval sequence: OOPS → Finance → Admin → SCM"

    try:
        # Fetch all active users belonging to any of the four approval roles
        placeholders = ", ".join(["%s"] * len(APPROVAL_ROLES))
        cursor.execute(
            f"""
            SELECT email, full_name, role
            FROM users
            WHERE LOWER(role) IN ({placeholders})
              AND is_active = 1
            """,
            APPROVAL_ROLES,
        )
        approvers = cursor.fetchall()

        if not approvers:
            print(f"⚠️ No active approver users found for lead {lead_id}")
            return

        sent_count = 0
        for user in approvers:
            role_label = role_display.get(user["role"].lower(), user["role"].upper())
            subject = f"[CRM] {role_label} Approval Required – Lead {lead_id}"
            body = f"""
            <div style="font-family: Arial, sans-serif; font-size:14px; color:#333; line-height:1.6;">

                <p>Dear {user['full_name']},</p>

                <p>
                A lead has been moved to the <b>KICK-OFF</b> stage and requires your approval.
                </p>

                <table style="border-collapse: collapse; width: 100%; margin-top: 10px;">
                <tr>
                    <td style="padding:8px; border:1px solid #ddd;"><b>Lead ID</b></td>
                    <td style="padding:8px; border:1px solid #ddd;">{lead_id}</td>
                </tr>
                <tr>
                    <td style="padding:8px; border:1px solid #ddd;"><b>Your Role</b></td>
                    <td style="padding:8px; border:1px solid #ddd;">{role_label}</td>
                </tr>
                <tr>
                    <td style="padding:8px; border:1px solid #ddd;"><b>Approval Flow</b></td>
                    <td style="padding:8px; border:1px solid #ddd;">OOPS → Finance → Admin → SCM</td>
                </tr>
            </table>

            <p style="margin-top:15px;">
                Please review and take necessary action.
            </p>

            <p>
                <a href="http://192.168.1.110:8000//leads/{lead_id}" 
                    style="color:white;padding:10px 15px;text-decoration:none;border-radius:5px;">
                    View Lead
                </a>
            </p>

            <br>

            <p>Best regards,<br>
            <b>Smart CRM System</b><br>
            Cogent Security</p>

        </div>
        """
            send_email(user["email"], subject, body)
            sent_count += 1

        print(f"✅ Kickoff emails sent to {sent_count} approver(s) for lead {lead_id}")

    except Exception as e:
        print(f"❌ send_kickoff_emails failed for lead {lead_id}: {e}")


def register_lead_report_routes(app):
    import uuid
    from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File, Form, Query
    from fastapi.responses import FileResponse
    from pathlib import Path
    from database import get_connection

    REPORTS_DIR = Path("uploads/reports")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    @app.post("/api/lead-report/upload/{lead_id}")
    async def upload_lead_report(lead_id: str, request: Request, file: UploadFile = File(...), name: str = Form(...), description: str = Form(...), user: dict = Depends(get_current_user)):
        if not check_user_permission(user, 'can_edit_leads'):
            raise HTTPException(status_code=403, detail="No permission to upload report.")
        if not file.filename.lower().endswith('.pdf') or file.content_type != 'application/pdf':
            raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
        report_id = str(uuid.uuid4())
        ext = Path(file.filename).suffix
        safe_name = f"{report_id}{ext}"
        lead_folder = REPORTS_DIR / lead_id
        lead_folder.mkdir(parents=True, exist_ok=True)
        file_path = lead_folder / safe_name
        with open(file_path, "wb") as f:
            f.write(await file.read())
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO lead_reports (id, lead_id, name, description, filename, uploaded_at, uploaded_by) VALUES (%s, %s, %s, %s, %s, NOW(), %s)",
                (report_id, lead_id, name, description, safe_name, user.get('username', 'Unknown'))
            )
        conn.commit()
        conn.close()
        return {"success": True}

    @app.get("/api/lead-report/list/{lead_id}")
    async def list_lead_reports(lead_id: str, user: dict = Depends(get_current_user)):
        if not check_user_permission(user, 'can_view_leads'):
            raise HTTPException(status_code=403, detail="No permission to view reports.")
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM lead_reports WHERE lead_id = %s ORDER BY uploaded_at DESC", (lead_id,))
            rows = cursor.fetchall()
        conn.close()
        return [{"id": r["id"], "name": r["name"], "description": r["description"], "filename": r["filename"], "uploaded_at": r["uploaded_at"].strftime('%Y-%m-%d %H:%M'), "uploaded_by": r["uploaded_by"]} for r in rows]

    @app.get("/api/lead-report/download/{report_id}")
    async def download_lead_report(report_id: str, format: str = Query("original"), user: dict = Depends(get_current_user)):
        if not check_user_permission(user, 'can_view_leads'):
            raise HTTPException(status_code=403, detail="No permission to download report.")
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM lead_reports WHERE id = %s", (report_id,))
            row = cursor.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Report not found.")
        file_path = REPORTS_DIR / row["lead_id"] / row["filename"]
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found.")
        ext = file_path.suffix.lower()
        if ext != ".pdf":
            raise HTTPException(status_code=400, detail="Only PDF files are available for download.")
        return FileResponse(str(file_path), filename=row["name"], media_type="application/pdf")

    @app.delete("/api/lead-report/delete/{report_id}")
    async def delete_lead_report(report_id: str, user: dict = Depends(get_current_user)):
        if not check_user_permission(user, 'can_edit_leads'):
            raise HTTPException(status_code=403, detail="No permission to delete report.")
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM lead_reports WHERE id = %s", (report_id,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                raise HTTPException(status_code=404, detail="Report not found.")
            file_path = REPORTS_DIR / row["lead_id"] / row["filename"]
            if file_path.exists():
                file_path.unlink()
            cursor.execute("DELETE FROM lead_reports WHERE id = %s", (report_id,))
        conn.commit()
        conn.close()
        return {"success": True}


from fastapi import HTTPException, Depends, status, Request, Response, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import hashlib
from datetime import datetime, date, timedelta, timezone
import os
import json
from enum import Enum
from contextlib import contextmanager
import secrets
import shutil
import uuid

from database import get_db, test_connection

from fastapi import Body

@app.post("/api/audit-log")
async def api_audit_log(request: Request, payload: dict = Body(...)):
    session_token = request.cookies.get("session_token")
    user_id = None
    username = None
    if session_token:
        try:
            session_data = validate_session_token(session_token)
            if session_data:
                user_id = session_data.get("user_id")
                username = session_data.get("username")
        except Exception:
            pass

    action = payload.get("action")
    details = payload.get("details", {})
    path = payload.get("path")
    resource = payload.get("resource") or details.get("resource") or '-'
    description = payload.get("description") or details.get("description") or '-'

    try:
        log_user_activity(
            request=request, user_id=user_id, username=username, action=action,
            resource_type=resource, resource_id=None, success=True, status_code=200,
            details=json.dumps(details), session_token=session_token, description=description,
        )
        return {"success": True}
    except Exception as e:
        print("Audit log error:", e)
        return {"success": False, "error": str(e)}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401 and "api" in request.url.path:
        return JSONResponse(status_code=401, content={"detail": exc.detail})
    elif exc.status_code == 403 and "api" in request.url.path:
        return JSONResponse(status_code=403, content={"detail": exc.detail})
    raise exc


app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

os.makedirs("templates", exist_ok=True)
os.makedirs("static", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

sessions = {}
SESSION_TIMEOUT = 3600


def get_db_connection():
    return get_db()


def dict_cursor(cursor):
    columns = [col[0] for col in cursor.description] if cursor.description else []
    def fetchall_dict():
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows] if rows else []
    def fetchone_dict():
        row = cursor.fetchone()
        return dict(zip(columns, row)) if row else None
    cursor.fetchall_dict = fetchall_dict
    cursor.fetchone_dict = fetchone_dict
    return cursor


class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    SALES = "sales"
    VIEWER = "viewer"


class UserPermissions(BaseModel):
    can_view_leads: bool = True
    can_create_leads: bool = True
    can_edit_leads: bool = True
    can_delete_leads: bool = False
    can_view_users: bool = False
    can_manage_users: bool = False
    can_view_reports: bool = True
    can_export_data: bool = True


class UserCreate(BaseModel):
    username: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: str
    email: str
    designation: Optional[str] = None
    mobile_no: Optional[str] = None
    date_of_birth: Optional[date] = None
    photo: Optional[str] = None
    role: UserRole = UserRole.SALES
    permissions: Optional[Dict[str, bool]] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[UserRole] = None
    permissions: Optional[Dict[str, bool]] = None
    is_active: Optional[bool] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class LeadCreate(BaseModel):
    lead_date: str
    lead_source: str
    lead_type: str
    lead_status: Optional[str] = None
    method_of_communication: Optional[str] = None
    lead_owner: Optional[str] = None
    assigned_to: Optional[int] = None
    staff_location: Optional[str] = None
    designation: str
    company_name: str
    industry_type: str
    system: str
    project_amc: str
    state: str
    district: str
    city: str
    pin_code: str
    full_address: str
    company_website: Optional[str] = None
    company_linkedin_link: Optional[str] = None
    sub_industry: Optional[str] = None
    gstin: Optional[str] = None
    customer_name: str
    contact_no: str
    landline_no: Optional[str] = None
    email_id: str
    linkedin_profile: Optional[str] = None
    designation_customer: Optional[str] = None
    margin_percent: Optional[float] = None
    gross_margin_amount: Optional[float] = None
    net_margin_amount: Optional[float] = None
    received_amount: Optional[float] = None
    balance_amount: Optional[float] = None
    lead_closer_date: Optional[str] = None
    expected_lead_closer_month: Optional[str] = None


class LeadUpdate(BaseModel):
    lead_type: Optional[str] = None
    lead_owner: Optional[str] = None
    assigned_to: Optional[int] = None
    designation: Optional[str] = None
    company_name: Optional[str] = None
    industry_type: Optional[str] = None
    sub_industry: Optional[str] = None
    system: Optional[str] = None
    project_amc: Optional[str] = None
    company_website: Optional[str] = None
    company_linkedin_profile: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    pin_code: Optional[str] = None
    full_address: Optional[str] = None
    customer_name: Optional[str] = None
    contact_no: Optional[str] = None
    landline_no: Optional[str] = None
    email_id: Optional[str] = None
    linkedin_profile: Optional[str] = None
    designation_customer: Optional[str] = None
    method_of_communication: Optional[str] = None
    lead_status: Optional[str] = None
    purpose_of_meeting: Optional[str] = None
    meeting_outcome: Optional[str] = None
    discussion_held: Optional[str] = None
    remarks: Optional[str] = None
    next_follow_up_date: Optional[str] = None
    prospect: Optional[str] = None
    approx_value: Optional[float] = None
    negotiated_value: Optional[float] = None
    closing_amount: Optional[float] = None
    gstin: Optional[str] = None
    lead_percentage: Optional[int] = None
    margin_percent: Optional[float] = None
    gross_margin_amount: Optional[float] = None
    net_margin_amount: Optional[float] = None
    received_amount: Optional[float] = None
    balance_amount: Optional[float] = None
    lead_closer_date: Optional[str] = None
    expected_lead_closer_month: Optional[str] = None


def generate_session_token():
    return secrets.token_urlsafe(32)


def create_session(user_id: int, username: str, role: str, permissions: Dict):
    session_token = generate_session_token()
    sessions[session_token] = {
        "user_id": user_id, "username": username, "role": role,
        "permissions": permissions, "created_at": datetime.now(), "last_activity": datetime.now()
    }
    return session_token


def validate_session_token(session_token: str) -> Optional[Dict]:
    if session_token not in sessions:
        return None
    session_data = sessions[session_token]
    if (datetime.now() - session_data["last_activity"]).seconds > SESSION_TIMEOUT:
        del sessions[session_token]
        return None
    session_data["last_activity"] = datetime.now()
    sessions[session_token] = session_data
    return session_data


def logout_session(session_token: str):
    if session_token in sessions:
        del sessions[session_token]
    return True


def log_user_activity(
    request, user_id, username, action,
    resource_type=None, resource_id=None, success=True,
    status_code=None, details=None, session_token=None, description=None,
):
    path = method = ip_address = user_agent = None
    try:
        if request is not None:
            path = str(request.url.path)
            method = request.method
            ip_address = request.headers.get("x-forwarded-for") or (request.client.host if request.client else None)
            user_agent = request.headers.get("user-agent")
    except Exception:
        pass

    def safe(val, default='N/A', int_field=False):
        if int_field:
            if val is None or val == '' or (isinstance(val, str) and not val.isdigit()):
                return None
            return int(val)
        return default if val is None or (isinstance(val, str) and not val.strip()) else val

    description = description or '-'
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO audit_logs (
                user_id, username, action, resource_type, resource_id,
                method, path, ip_address, user_agent, status_code,
                success, details, session_token, description
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ''', (
            safe(user_id, None, int_field=True), safe(username, '-'), safe(action, '-'),
            safe(resource_type, '-'), safe(resource_id, '-'), safe(method, '-'),
            safe(path, '-'), safe(ip_address, '-'), safe(user_agent, '-'),
            safe(status_code, '-'), 1 if success else 0, safe(details, '-'),
            safe(session_token, '-'), safe(description, '-')
        ))
        conn.commit()


def generate_lead_id():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT setting_data FROM lead_settings WHERE setting_type = 'preferences'")
        prefs_row = cursor.fetchone()
        prefix = 'CS'
        start_number = 1000000001
        if prefs_row:
            try:
                prefs = json.loads(prefs_row['setting_data'])
                prefix = prefs.get('leadIdPrefix', 'CS').strip() or 'CS'
                start_number = int(prefs.get('leadIdStart', 1000000001))
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        cursor.execute("SELECT lead_id FROM leads ORDER BY id DESC LIMIT 1")
        last_lead = cursor.fetchone()
        if last_lead:
            try:
                last_id = last_lead['lead_id']
                num_part = last_id[len(prefix):] if last_id.startswith(prefix) else last_id
                new_number = int(num_part) + 1
            except (ValueError, KeyError, TypeError, IndexError):
                new_number = start_number
        else:
            new_number = start_number
        return f"{prefix}{new_number:010d}"


def get_preferences():
    defaults = {
        'leadIdPrefix': 'CS', 'leadIdStart': 1000000001, 'followUpDays': 7,
        'agingAlertDays': 30, 'emailNotifications': True, 'dailyDigest': True,
        'defaultPageSize': 20, 'autoLeadPercentage': False
    }
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT setting_data FROM lead_settings WHERE setting_type = 'preferences'")
            prefs_row = cursor.fetchone()
            if prefs_row:
                prefs = json.loads(prefs_row['setting_data'])
                return {**defaults, **prefs}
    except Exception:
        pass
    return defaults


def get_status_percentages():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT setting_data FROM lead_settings WHERE setting_type = 'status_percentages'")
            row = cursor.fetchone()
            if row and row['setting_data']:
                data = json.loads(row['setting_data'])
                if isinstance(data, dict) and data:
                    return data
    except Exception as e:
        print(f"⚠️ Error fetching status percentages: {e}")
    return {}


def calculate_lead_percentage(lead_status: str) -> int:
    mappings = get_status_percentages()
    if lead_status and lead_status in mappings:
        try:
            return int(mappings[lead_status])
        except (ValueError, TypeError):
            pass
    return 0


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def seed_permissions(cursor):
    def add_perm(key, name, parent_id, category, level, desc=""):
        cursor.execute('''
        INSERT INTO permissions (permission_key, permission_name, parent_id, category, level, description)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (key, name, parent_id, category, level, desc))
        return cursor.lastrowid

    dashboard_id = add_perm("dashboard", "Dashboard", None, "page", 0, "Access to dashboard page")
    leads_id = add_perm("leads", "Leads", None, "page", 0, "Access to leads page")
    add_lead_id = add_perm("add_lead", "Add Lead", None, "page", 0, "Access to add lead page")
    target_id = add_perm("target_management", "Target Management", None, "page", 0, "Access to target management")
    settings_id = add_perm("lead_settings", "Lead Settings", None, "page", 0, "Access to lead settings")
    users_id = add_perm("users", "Users", None, "page", 0, "Access to users management")
    control_id = add_perm("control_panel", "Control Panel", None, "page", 0, "Access to control panel")

    dash_kpis_id = add_perm("dashboard.view_kpis", "View KPIs", dashboard_id, "feature", 1, "View all KPIs")
    for kpi in ["total_leads", "qualified_leads", "won_deals", "total_revenue", "avg_lead_value", "conversion_rate"]:
        add_perm(f"dashboard.kpi.{kpi}", f"{kpi.replace('_',' ').title()} KPI", dash_kpis_id, "kpi", 2)

    dash_charts_id = add_perm("dashboard.view_charts", "View Charts", dashboard_id, "feature", 1)
    for chart in ["revenue", "lead_source", "monthly_trend", "status_distribution"]:
        add_perm(f"dashboard.chart.{chart}", f"{chart.replace('_',' ').title()} Chart", dash_charts_id, "chart", 2)

    add_perm("leads.view_table", "View Leads Table", leads_id, "feature", 1)
    leads_actions_id = add_perm("leads.actions", "Lead Actions", leads_id, "feature", 1)
    for action in ["add", "edit", "delete", "export", "bulk"]:
        add_perm(f"leads.action.{action}", f"{action.title()} Lead", leads_actions_id, "action", 2)

    leads_cols_id = add_perm("leads.table_columns", "Table Columns", leads_id, "feature", 1)
    columns = ["lead_id","lead_date","company_name","customer_name","contact_no","landline_no","email_id",
               "lead_source","lead_type","lead_status","lead_owner","assigned_to","industry_type",
               "state","city","method_of_communication","next_follow_up_date","prospect","purpose_of_meeting",
               "approx_value","negotiated_value","closing_amount","lead_percentage","lead_aging",
               "meeting_outcome","discussion_held","remarks"]
    for col in columns:
        add_perm(f"leads.column.{col}", f"{col.replace('_',' ').title()} Column", leads_cols_id, "column", 2)

    leads_view_id = add_perm("leads.fields_view", "View Lead Fields", leads_id, "feature", 1)
    fields = ["lead_id","lead_date","lead_source","lead_type","lead_owner","designation","company_name",
              "industry_type","system","project_amc","state","district","city","pin_code","full_address",
              "company_website","company_linkedin_link","sub_industry","gstin","customer_name","contact_no",
              "landline_no","email_id","linkedin_profile","designation_customer","method_of_communication",
              "lead_status","purpose_of_meeting","meeting_outcome","discussion_held","remarks",
              "next_follow_up_date","prospect","approx_value","negotiated_value","closing_amount",
              "lead_aging","lead_percentage","created_by","assigned_to","created_at","updated_at"]
    for field in fields:
        add_perm(f"leads.field.view.{field}", f"View {field.replace('_',' ').title()}", leads_view_id, "field", 2)

    leads_edit_id = add_perm("leads.fields_edit", "Edit Lead Fields", leads_id, "feature", 1)
    for field in fields:
        add_perm(f"leads.field.edit.{field}", f"Edit {field.replace('_',' ').title()}", leads_edit_id, "field", 2)

    add_perm("add_lead.view_form", "View Add Lead Form", add_lead_id, "feature", 1)
    add_lead_fields_id = add_perm("add_lead.fields", "Add Lead Form Fields", add_lead_id, "feature", 1)
    for field in fields[:35]:
        add_perm(f"add_lead.field.{field}", f"{field.replace('_',' ').title()} Field", add_lead_fields_id, "field", 2)
    add_perm("add_lead.action.submit", "Submit New Lead", add_lead_id, "action", 1)

    for action in ["view_page", "action.add", "action.edit", "action.delete"]:
        add_perm(f"target_management.{action}", f"Target {action.replace('_',' ').title()}", target_id, "feature" if "view" in action else "action", 1)

    settings_tabs_id = add_perm("lead_settings.tabs", "Settings Tabs", settings_id, "feature", 1)
    tabs = ["status","source","type","industry","communication_method","sub_industry","designation","system","project_amc","state","district","prospect","purpose_of_meeting"]
    for tab in tabs:
        add_perm(f"lead_settings.tab.{tab}", f"{tab.replace('_',' ').title()} Tab", settings_tabs_id, "tab", 2)
    add_perm("lead_settings.action.edit", "Edit Settings", settings_id, "action", 1)

    add_perm("users.view_page", "View Users", users_id, "feature", 1)
    for action in ["add", "edit", "delete"]:
        add_perm(f"users.action.{action}", f"{action.title()} User", users_id, "action", 1)
    add_perm("users.manage_permissions", "Manage User Permissions", users_id, "action", 1)

    add_perm("control_panel.view_page", "View Control Panel", control_id, "feature", 1)
    add_perm("control_panel.backup", "Database Backup", control_id, "action", 1)
    add_perm("control_panel.audit_logs", "View Audit Logs", control_id, "feature", 1)

    cursor.execute('SELECT COUNT(*) as count FROM permissions')
    result = cursor.fetchone()
    print(f"✅ {result['count'] if result else 0} permissions seeded!")


def init_database():
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lead_reports (
            id VARCHAR(64) PRIMARY KEY,
            lead_id VARCHAR(64),
            name VARCHAR(255),
            description TEXT,
            filename VARCHAR(255),
            uploaded_at DATETIME,
            uploaded_by VARCHAR(128)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS designations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            first_name VARCHAR(255),
            last_name VARCHAR(255),
            full_name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL,
            designation VARCHAR(255),
            mobile_no VARCHAR(50),
            date_of_birth DATE,
            photo TEXT,
            role VARCHAR(50) NOT NULL,
            permissions TEXT,
            is_active TINYINT(1) DEFAULT 1,
            created_by INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP NULL
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INT AUTO_INCREMENT PRIMARY KEY,
            lead_id VARCHAR(255) UNIQUE NOT NULL,
            lead_date DATE NOT NULL,
            lead_source VARCHAR(255),
            lead_type VARCHAR(255),
            lead_owner VARCHAR(255),
            staff_location VARCHAR(255),
            designation VARCHAR(255),
            company_name VARCHAR(500) NOT NULL,
            industry_type VARCHAR(255),
            `system` VARCHAR(255),
            project_amc VARCHAR(255),
            state VARCHAR(255),
            district VARCHAR(255),
            city VARCHAR(255),
            pin_code VARCHAR(20),
            full_address TEXT,
            company_website VARCHAR(500),
            company_linkedin_link VARCHAR(500),
            sub_industry VARCHAR(255),
            gstin VARCHAR(50),
            customer_name VARCHAR(255) NOT NULL,
            contact_no VARCHAR(50) NOT NULL,
            landline_no VARCHAR(50),
            email_id VARCHAR(255) NOT NULL,
            linkedin_profile VARCHAR(500),
            designation_customer VARCHAR(255),
            method_of_communication VARCHAR(100) DEFAULT 'Email',
            lead_status VARCHAR(100) DEFAULT 'New',
            purpose_of_meeting TEXT,
            meeting_outcome TEXT,
            discussion_held TEXT,
            remarks TEXT,
            next_follow_up_date DATE,
            prospect VARCHAR(255),
            approx_value DECIMAL(15,2),
            negotiated_value DECIMAL(15,2),
            closing_amount DECIMAL(15,2),
            margin_percent DECIMAL(7,2),
            gross_margin_amount DECIMAL(15,2),
            net_margin_amount DECIMAL(15,2),
            received_amount DECIMAL(15,2),
            balance_amount DECIMAL(15,2),
            payment_term VARCHAR(255),
            lead_closer_date DATE,
            expected_lead_closer_month VARCHAR(20),
            lead_aging INT DEFAULT 0,
            lead_percentage INT DEFAULT 0,
            approval_status VARCHAR(50) DEFAULT NULL,
            current_approval_level VARCHAR(50) DEFAULT NULL,
            procurement_allowed TINYINT(1) DEFAULT 0,
            created_by INT NOT NULL,
            assigned_to INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id),
            FOREIGN KEY (assigned_to) REFERENCES users(id)
        )
        ''')

        # Add landline_no column if missing (existing DBs)
        try:
            cursor.execute("ALTER TABLE leads ADD COLUMN landline_no VARCHAR(50) AFTER contact_no")
            conn.commit()
            print("✅ landline_no column added to leads table")
        except Exception:
            pass

        # Add approval columns if missing (existing DBs)
        for col_sql in [
            "ALTER TABLE leads ADD COLUMN approval_status VARCHAR(50) DEFAULT NULL",
            "ALTER TABLE leads ADD COLUMN current_approval_level VARCHAR(50) DEFAULT NULL",
            "ALTER TABLE leads ADD COLUMN procurement_allowed TINYINT(1) DEFAULT 0",
        ]:
            try:
                cursor.execute(col_sql)
                conn.commit()
            except Exception:
                pass

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lead_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            lead_id VARCHAR(255) NOT NULL,
            field_name VARCHAR(255) NOT NULL,
            old_value TEXT,
            new_value TEXT,
            changed_by INT NOT NULL,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (changed_by) REFERENCES users(id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lead_status_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            lead_id VARCHAR(255) NOT NULL,
            old_status VARCHAR(100),
            new_status VARCHAR(100),
            remarks TEXT,
            changed_by INT NOT NULL,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (changed_by) REFERENCES users(id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lead_activities (
            id INT AUTO_INCREMENT PRIMARY KEY,
            lead_id VARCHAR(255) NOT NULL,
            activity_type VARCHAR(100) NOT NULL,
            description TEXT NOT NULL,
            activity_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            performed_by INT NOT NULL,
            FOREIGN KEY (performed_by) REFERENCES users(id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lead_settings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            setting_type VARCHAR(255) NOT NULL UNIQUE,
            setting_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            updated_by INT,
            FOREIGN KEY (updated_by) REFERENCES users(id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_settings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            setting_key VARCHAR(255) NOT NULL UNIQUE,
            setting_value TEXT NOT NULL,
            setting_type VARCHAR(50) DEFAULT 'string',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            updated_by INT,
            FOREIGN KEY (updated_by) REFERENCES users(id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            username VARCHAR(255),
            action VARCHAR(255) NOT NULL,
            resource_type VARCHAR(255),
            resource_id VARCHAR(255),
            method VARCHAR(50),
            path TEXT,
            ip_address VARCHAR(50),
            user_agent TEXT,
            status_code INT,
            success TINYINT(1),
            details TEXT,
            session_token VARCHAR(255),
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        ''')

        for idx_sql in [
            "CREATE INDEX idx_audit_user_time ON audit_logs(user_id, created_at)",
            "CREATE INDEX idx_audit_action_resource ON audit_logs(action, resource_type)",
        ]:
            try:
                cursor.execute(idx_sql)
            except Exception:
                pass

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS targets (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            type VARCHAR(100) NOT NULL,
            target_value DECIMAL(15,2) NOT NULL,
            current_value DECIMAL(15,2) DEFAULT 0,
            assigned_to INT NOT NULL,
            period VARCHAR(100) NOT NULL,
            context_tab VARCHAR(100),
            description TEXT,
            is_active TINYINT(1) DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            created_by INT,
            FOREIGN KEY (assigned_to) REFERENCES users(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS permissions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            permission_key VARCHAR(255) UNIQUE NOT NULL,
            permission_name VARCHAR(255) NOT NULL,
            parent_id INT,
            category VARCHAR(100) NOT NULL,
            level INT DEFAULT 0,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_id) REFERENCES permissions(id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_permissions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            permission_id INT NOT NULL,
            granted TINYINT(1) DEFAULT 1,
            granted_by INT,
            granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (permission_id) REFERENCES permissions(id),
            FOREIGN KEY (granted_by) REFERENCES users(id),
            UNIQUE(user_id, permission_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lead_approvals (
            id INT AUTO_INCREMENT PRIMARY KEY,
            lead_id INT NOT NULL,
            approval_level VARCHAR(50),
            action VARCHAR(20),
            comment TEXT,
            approved_by INT,
            approved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads(id),
            FOREIGN KEY (approved_by) REFERENCES users(id)
        )
        ''')

        # ✅ REMOVED: vendors table creation

        for idx_sql in [
            "CREATE INDEX idx_permissions_key ON permissions(permission_key)",
            "CREATE INDEX idx_permissions_parent ON permissions(parent_id)",
            "CREATE INDEX idx_user_permissions_user ON user_permissions(user_id)",
            "CREATE INDEX idx_user_permissions_perm ON user_permissions(permission_id)",
        ]:
            try:
                cursor.execute(idx_sql)
            except Exception:
                pass

        cursor.execute('SELECT COUNT(*) as count FROM permissions')
        perm_count_result = cursor.fetchone()
        if (perm_count_result['count'] if perm_count_result else 0) == 0:
            print("🔐 Seeding permissions...")
            seed_permissions(cursor)

        cursor.execute('SELECT COUNT(*) as count FROM users WHERE role = %s', ("admin",))
        result = cursor.fetchone()
        if (result['count'] if result else 0) == 0:
            default_admin_permissions = {
                'can_view_leads': True, 'can_create_leads': True, 'can_edit_leads': True,
                'can_delete_leads': True, 'can_view_users': True, 'can_manage_users': True,
                'can_view_reports': True, 'can_export_data': True
            }
            cursor.execute('''
            INSERT INTO users (username, password, full_name, email, role, permissions, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', ('admin', hash_password("admin123"), 'Administrator', 'admin@crm.com',
                  'admin', json.dumps(default_admin_permissions), 1))
            admin_user_id = cursor.lastrowid
            cursor.execute('SELECT id FROM permissions')
            all_perms = cursor.fetchall()
            for perm in all_perms:
                cursor.execute('''
                INSERT INTO user_permissions (user_id, permission_id, granted, granted_by)
                VALUES (%s, %s, 1, %s)
                ''', (admin_user_id, perm['id'], admin_user_id))
            print(f"✅ Admin user created with {len(all_perms)} permissions")
        else:
            cursor.execute('SELECT id FROM users WHERE role = %s', ("admin",))
            admin_users = cursor.fetchall()
            cursor.execute('SELECT id FROM permissions')
            all_perms = cursor.fetchall()
            for admin in admin_users:
                for perm in all_perms:
                    try:
                        cursor.execute('''
                        INSERT IGNORE INTO user_permissions (user_id, permission_id, granted, granted_by)
                        VALUES (%s, %s, 1, %s)
                        ''', (admin['id'], perm['id'], admin['id']))
                    except Exception:
                        pass

        conn.commit()
        cursor.close()
        print("✅ MySQL Database initialized successfully!")


_db_initialized = False

def ensure_db_initialized():
    global _db_initialized
    if not _db_initialized:
        print("🔄 Initializing database...")
        init_database()
        _db_initialized = True


@app.on_event("startup")
async def startup_event():
    try:
        ensure_db_initialized()
        print("✅ Application started successfully!")
    except Exception as e:
        import traceback
        print(f"⚠️ Database initialization failed: {type(e).__name__}: {str(e)}")
        traceback.print_exc()


def get_current_user(request: Request):
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    session_data = validate_session_token(session_token)
    if not session_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or invalid")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = %s', (session_data["user_id"],))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        permissions = json.loads(user['permissions']) if user['permissions'] else {}
        cursor.execute('''
        SELECT p.permission_key FROM user_permissions up
        JOIN permissions p ON up.permission_id = p.id
        WHERE up.user_id = %s AND up.granted = 1 ORDER BY p.permission_key
        ''', (user['id'],))
        perm_rows = cursor.fetchall()
        permission_keys = [r['permission_key'] for r in perm_rows] if perm_rows else []
        return {
            "user_id": user['id'], "username": user['username'], "full_name": user['full_name'],
            "email": user['email'], "role": user['role'], "permissions": permissions,
            "permission_keys": permission_keys, "is_admin": user['role'] == 'admin',
            "session_token": session_token
        }


LEGACY_PERMISSION_ALIASES = {
    "can_view_leads": ["leads", "leads.view_table"],
    "can_create_leads": ["add_lead", "leads.action.add"],
    "can_edit_leads": ["leads.action.edit"],
    "can_delete_leads": ["leads.action.delete"],
    "can_view_users": ["users", "control_panel"],
    "can_manage_users": ["control_panel", "users"],
}


def _has_permission_in_keys(permission: str, permission_keys: List[str]) -> bool:
    if not permission:
        return True
    if not permission_keys:
        return False
    if permission in permission_keys:
        return True
    parts = permission.split('.')
    for i in range(len(parts), 0, -1):
        if '.'.join(parts[:i]) in permission_keys:
            return True
    return any(key.startswith(f"{permission}.") for key in permission_keys)


def check_user_permission(user: dict, permission: str):
    if not permission:
        return True
    if user.get('role') == 'admin' or user.get('is_admin'):
        return True
    permission_keys = user.get('permission_keys') or []
    if _has_permission_in_keys(permission, permission_keys):
        return True
    for alias in LEGACY_PERMISSION_ALIASES.get(permission, []):
        if _has_permission_in_keys(alias, permission_keys):
            return True
    return (user.get('permissions') or {}).get(permission, False)


register_lead_report_routes(app)


def resolve_default_route(user: dict) -> str:
    preferred_routes = [
        ("dashboard", "/dashboard"), ("leads", "/leads"), ("add_lead", "/add-lead"),
        ("target_management", "/target-management"), ("lead_settings", "/lead-settings"),
        ("users", "/users"), ("control_panel", "/control-panel"),
    ]
    for key, path in preferred_routes:
        if check_user_permission(user, key):
            return path
    if (user.get('permissions') or {}).get('can_view_leads'):
        return "/leads"
    return "/dashboard"


# ========== PAGE ROUTES ==========

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/permission-management", response_class=HTMLResponse)
async def permission_management_page(request: Request, user: dict = Depends(get_current_user)):
    if user['role'] != 'admin':
        return templates.TemplateResponse("error.html", {"request": request, "error": "Access Denied", "message": "Only administrators can access permission management."})
    return templates.TemplateResponse("permission_management.html", {"request": request, "user": user})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: dict = Depends(get_current_user)):
    if not check_user_permission(user, 'dashboard'):
        return RedirectResponse(url="/leads", status_code=302)
    stats = {}
    with get_db_connection() as conn:
        cursor = conn.cursor()
        where_clause = ""
        params = []
        if user['role'] != 'admin':
            where_clause = "AND (created_by = %s OR assigned_to = %s)"
            params = [user['user_id'], user['user_id']]

        cursor.execute(f'SELECT COUNT(*) as count FROM leads WHERE 1=1 {where_clause}', params)
        result = cursor.fetchone()
        total_leads = result['count'] if result else 0

        prefs = get_preferences()
        follow_up_days = int(prefs.get('followUpDays', 7))

        cursor.execute(f'''SELECT COUNT(*) as count FROM leads
            WHERE next_follow_up_date >= CURDATE()
            AND next_follow_up_date <= DATE_ADD(CURDATE(), INTERVAL {follow_up_days} DAY) {where_clause}''', params)
        upcoming_result = cursor.fetchone()
        upcoming_followups = upcoming_result['count'] if upcoming_result else 0

        cursor.execute(f'''SELECT COUNT(*) as count FROM leads
            WHERE next_follow_up_date IS NOT NULL AND next_follow_up_date < CURDATE() {where_clause}''', params)
        missed_result = cursor.fetchone()
        missed_followups = missed_result['count'] if missed_result else 0

        cursor.execute(f'SELECT lead_status, COUNT(*) as count FROM leads WHERE 1=1 {where_clause} GROUP BY lead_status ORDER BY count DESC', params)
        leads_by_status = cursor.fetchall()

        cursor.execute(f'SELECT lead_id, company_name, customer_name, lead_status, updated_at, created_at FROM leads WHERE 1=1 {where_clause} ORDER BY updated_at DESC LIMIT 10', params)
        recent_leads = cursor.fetchall()

        cursor.execute(f'SELECT COALESCE(SUM(approx_value),0) as total_proposed, COALESCE(SUM(negotiated_value),0) as total_negotiated, COALESCE(SUM(closing_amount),0) as total_closing FROM leads WHERE 1=1 {where_clause}', params)
        value_result = cursor.fetchone()

        if user['role'] != 'admin':
            cursor.execute('SELECT t.*, u.full_name as assigned_to_name FROM targets t LEFT JOIN users u ON t.assigned_to = u.id WHERE t.is_active = 1 AND t.assigned_to = %s ORDER BY t.created_at DESC LIMIT 10', [user['user_id']])
        else:
            cursor.execute('SELECT t.*, u.full_name as assigned_to_name FROM targets t LEFT JOIN users u ON t.assigned_to = u.id WHERE t.is_active = 1 ORDER BY t.created_at DESC LIMIT 10')
        targets_data = cursor.fetchall()

        stats = {
            "total_leads": total_leads, "upcoming_followups": upcoming_followups, "missed_followups": missed_followups,
            "leads_by_status": [dict(s) for s in leads_by_status] if leads_by_status else [],
            "recent_leads": [dict(l) for l in recent_leads] if recent_leads else [],
            "value_metrics": {
                "total_proposed": float(value_result['total_proposed']) if value_result else 0,
                "total_negotiated": float(value_result['total_negotiated']) if value_result else 0,
                "total_closing": float(value_result['total_closing']) if value_result else 0
            },
            "targets": [dict(t) for t in targets_data] if targets_data else []
        }

    return templates.TemplateResponse("dashboard.html", {
        "request": request, "user": user, "today": date.today().isoformat(),
        "stats": stats, "follow_up_days": follow_up_days
    })

@app.get("/leads", response_class=HTMLResponse)
async def leads_page(request: Request, user: dict = Depends(get_current_user)):
    if not check_user_permission(user, 'can_view_leads'):
        raise HTTPException(status_code=403, detail="You don't have permission to view leads")
    prefs = get_preferences()
    return templates.TemplateResponse("leads.html", {
        "request": request, "user": user, "today": date.today().isoformat(),
        "follow_up_days": int(prefs.get('followUpDays', 7)),
        "aging_alert_days": int(prefs.get('agingAlertDays', 30))
    })

@app.get("/add-lead", response_class=HTMLResponse)
async def add_lead_page(request: Request, user: dict = Depends(get_current_user)):
    if not check_user_permission(user, 'can_create_leads'):
        raise HTTPException(status_code=403, detail="You don't have permission to create leads")
    return templates.TemplateResponse("add_lead.html", {"request": request, "user": user, "today": date.today().isoformat()})

@app.get("/lead-detail/{lead_id}", response_class=HTMLResponse)
async def lead_detail_page(request: Request, lead_id: str, user: dict = Depends(get_current_user)):
    if not check_user_permission(user, 'can_view_leads'):
        raise HTTPException(status_code=403, detail="You don't have permission to view leads")
    with get_db_connection() as conn:
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM leads WHERE lead_id = %s", (lead_id,))
        lead_data = cursor.fetchone()
        if not lead_data:
            raise HTTPException(status_code=404, detail="Lead not found")
    return templates.TemplateResponse("lead_detail.html", {
        "request": request, "user": user, "lead_id": lead_id,
        "lead": lead_data, "today": date.today().isoformat()
    })

@app.get("/lead-reports/{lead_id}", response_class=HTMLResponse)
async def lead_reports_page(request: Request, lead_id: str, user: dict = Depends(get_current_user)):
    if not check_user_permission(user, 'can_view_leads'):
        raise HTTPException(status_code=403, detail="You don't have permission to view lead reports")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM lead_reports WHERE lead_id = %s ORDER BY uploaded_at DESC", (lead_id,))
        rows = cursor.fetchall()
    reports = [{"id": r["id"], "name": r["name"], "description": r["description"], "filename": r["filename"],
                "uploaded_at": r["uploaded_at"].strftime('%Y-%m-%d %H:%M') if r["uploaded_at"] else None,
                "uploaded_by": r["uploaded_by"]} for r in rows]
    return templates.TemplateResponse("lead_reports.html", {
        "request": request, "user": user, "lead_id": lead_id,
        "today": date.today().isoformat(), "reports": reports
    })

@app.get("/edit-lead/{lead_id}", response_class=HTMLResponse)
async def edit_lead_page(request: Request, lead_id: str, user: dict = Depends(get_current_user)):
    if not check_user_permission(user, 'can_edit_leads'):
        raise HTTPException(status_code=403, detail="You don't have permission to edit leads")
    return templates.TemplateResponse("edit_lead.html", {"request": request, "user": user, "lead_id": lead_id, "today": date.today().isoformat()})

@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, user: dict = Depends(get_current_user)):
    if not check_user_permission(user, 'can_view_users'):
        raise HTTPException(status_code=403, detail="You don't have permission to view users")
    return templates.TemplateResponse("users.html", {"request": request, "user": user, "today": date.today().isoformat()})

@app.get("/control-panel", response_class=HTMLResponse)
async def control_panel_page(request: Request, user: dict = Depends(get_current_user)):
    if not check_user_permission(user, 'can_view_users'):
        raise HTTPException(status_code=403, detail="You don't have permission to access control panel")
    return templates.TemplateResponse("control_panel.html", {"request": request, "user": user, "today": date.today().isoformat()})

@app.get("/lead-settings", response_class=HTMLResponse)
async def lead_settings_page(request: Request, user: dict = Depends(get_current_user)):
    if not check_user_permission(user, 'can_manage_users'):
        raise HTTPException(status_code=403, detail="You don't have permission to access lead settings")
    return templates.TemplateResponse("lead_settings.html", {"request": request, "user": user, "today": date.today().isoformat()})

@app.get("/target-management", response_class=HTMLResponse)
async def target_management_page(request: Request, user: dict = Depends(get_current_user)):
    return templates.TemplateResponse("target_management.html", {"request": request, "user": user, "today": date.today().isoformat()})

@app.get("/security-audit", response_class=HTMLResponse)
async def security_audit_page(request: Request, user: dict = Depends(lambda: {"role": "admin"})):
    return templates.TemplateResponse("security_audit.html", {"request": request, "user": user})


# ========== API ROUTES ==========

@app.post("/api/login")
async def login(login_data: LoginRequest, response: Response):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        hashed_password = hash_password(login_data.password)
        cursor.execute('SELECT * FROM users WHERE username = %s AND is_active = 1', (login_data.username,))
        user = cursor.fetchone()
        if not user or hashed_password != user['password']:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        permissions = json.loads(user['permissions']) if user['permissions'] else {}
        cursor.execute('''
        SELECT p.permission_key FROM user_permissions up
        JOIN permissions p ON up.permission_id = p.id
        WHERE up.user_id = %s AND up.granted = 1 ORDER BY p.permission_key
        ''', (user['id'],))
        permission_keys = [r['permission_key'] for r in cursor.fetchall()]
        cursor.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s', (user['id'],))
        conn.commit()
        user_payload = {
            "user_id": user['id'], "username": user['username'], "full_name": user['full_name'],
            "email": user['email'], "role": user['role'], "permissions": permissions,
            "permission_keys": permission_keys, "is_admin": user['role'] == 'admin'
        }
        redirect_to = resolve_default_route(user_payload)
        session_token = create_session(user_id=user['id'], username=user['username'], role=user['role'], permissions=permissions)
        response.set_cookie(key="session_token", value=session_token, httponly=True, secure=False, samesite="lax", max_age=SESSION_TIMEOUT)
        try:
            log_user_activity(request=None, user_id=user['id'], username=user['username'], action="login",
                              resource_type="session", resource_id=session_token, success=True, status_code=200,
                              details="User login successful", session_token=session_token)
        except Exception:
            pass
        return {"success": True, "user": user_payload, "session_token": session_token, "redirect_to": redirect_to}

@app.post("/api/logout")
async def logout(request: Request, response: Response):
    session_token = request.cookies.get("session_token")
    if session_token:
        session_data = validate_session_token(session_token)
        user_id = session_data["user_id"] if session_data else None
        username = session_data["username"] if session_data else None
        logout_session(session_token)
        try:
            log_user_activity(request=request, user_id=user_id, username=username, action="logout",
                              resource_type="session", resource_id=session_token, success=True, status_code=200,
                              details="User logout", session_token=session_token)
        except Exception:
            pass
    response.delete_cookie(key="session_token")
    return RedirectResponse(url="/login", status_code=302)

@app.get("/api/validate-session")
async def validate_session(request: Request):
    try:
        session_token = request.cookies.get("session_token")
        if not session_token:
            return JSONResponse(status_code=401, content={"success": False, "detail": "No session token"})
        session_data = validate_session_token(session_token)
        if not session_data:
            return JSONResponse(status_code=401, content={"success": False, "detail": "Session expired"})
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, username, full_name, email, role, permissions FROM users WHERE id = %s', (session_data["user_id"],))
            user = cursor.fetchone()
            if not user:
                return JSONResponse(status_code=401, content={"success": False, "detail": "User not found"})
            permissions = json.loads(user['permissions']) if user['permissions'] else {}
            return JSONResponse(status_code=200, content={"success": True, "user": {
                "user_id": user['id'], "username": user['username'], "full_name": user['full_name'],
                "email": user['email'], "role": user['role'], "permissions": permissions
            }})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "detail": str(e)})

# ============================================================
# REPLACE your existing @app.get("/api/leads") with this
# The only change is adding  filter: Optional[str] = None
# and the corresponding WHERE clause for missed follow-ups
# ============================================================

@app.get("/api/leads")
async def get_leads(
    request: Request,
    status: Optional[str] = None,
    owner: Optional[str] = None,
    search: Optional[str] = None,
    filter: Optional[str] = Query(None),   # ← Add Query()
    page: int = 1,
    limit: int = 20,
    user: dict = Depends(get_current_user)
):
    if not check_user_permission(user, 'can_view_leads'):
        raise HTTPException(status_code=403, detail="No permission to view leads")

    with get_db_connection() as conn:
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        query = '''SELECT l.*, u1.full_name as created_by_name, u2.full_name as assigned_to_name
                   FROM leads l
                   LEFT JOIN users u1 ON l.created_by = u1.id
                   LEFT JOIN users u2 ON l.assigned_to = u2.id
                   WHERE 1=1'''
        params = []

        # Role-based scoping
        user_role = (user.get('role') or '').strip().lower()
        if user_role != 'admin':
            query += ' AND (l.created_by = %s OR l.assigned_to = %s OR LOWER(l.current_approval_level) = %s)'
            params.extend([user['user_id'], user['user_id'], user_role])

        # Status filter
        if status:
            query += ' AND l.lead_status = %s'
            params.append(status)

        # Owner filter
        if owner:
            query += ' AND l.lead_owner = %s'
            params.append(owner)

        # Search filter
        if search:
            search_term = f'%{search}%'
            query += ' AND (l.lead_id LIKE %s OR l.company_name LIKE %s OR l.customer_name LIKE %s OR l.email_id LIKE %s OR l.contact_no LIKE %s)'
            params.extend([search_term] * 5)

        # ===== MISSED FOLLOW-UPS FILTER =====
        # Shows leads where next_follow_up_date is in the past and lead is not closed/won
        if filter == 'missed':
            query += ''' AND l.next_follow_up_date IS NOT NULL
                         AND l.next_follow_up_date < CURDATE()'''

        # Count total matching records
        # Count total matching records — use same params WITHOUT pagination
        count_params = [p for p in params]  # copy before adding LIMIT/OFFSET
        count_query = (
            "SELECT COUNT(*) as count FROM ("
            + query.replace(
                "SELECT l.*, u1.full_name as created_by_name, u2.full_name as assigned_to_name",
                "SELECT l.id"
            )
            + ") AS lead_count"
        )
        cursor.execute(count_query, count_params)
        count_result = cursor.fetchone()
        total = count_result['count'] if count_result else 0

# Now add pagination params
        if filter == 'missed':
            query += ' ORDER BY l.next_follow_up_date ASC LIMIT %s OFFSET %s'
        else:
            query += ' ORDER BY l.updated_at DESC LIMIT %s OFFSET %s'

        params.extend([limit, (page - 1) * limit])
        cursor.execute(query, params)
        leads = cursor.fetchall()
        leads_list = [dict(lead) for lead in leads] if leads else []

        # Normalize timestamps and calculate computed fields
        for l in leads_list:
            for ts_field in ("created_at", "updated_at"):
                val = l.get(ts_field)
                if isinstance(val, str) and val:
                    try:
                        l[ts_field] = datetime.strptime(val, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).isoformat()
                    except Exception:
                        pass
            ld = l.get("created_at") or l.get("lead_date")
            if ld:
                try:
                    date_str = str(ld).split("T")[0].split(" ")[0]
                    l["lead_aging"] = max(0, (date.today() - datetime.strptime(date_str, "%Y-%m-%d").date()).days)
                except Exception:
                    pass
            if not l.get("lead_percentage"):
                l["lead_percentage"] = calculate_lead_percentage(l.get("lead_status", "New"))

        return {
            "success": True,
            "data": leads_list,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit if limit > 0 else 0
            }
        }


@app.get("/api/leads/{lead_id}")
async def get_lead_detail(lead_id: str, request: Request, user: dict = Depends(get_current_user)):
    if not check_user_permission(user, 'can_view_leads'):
        raise HTTPException(status_code=403, detail="No permission to view leads")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if user['role'] != 'admin':
            cursor.execute('''
            SELECT l.*, u1.full_name as created_by_name, u2.full_name as assigned_to_name
            FROM leads l LEFT JOIN users u1 ON l.created_by = u1.id LEFT JOIN users u2 ON l.assigned_to = u2.id
            WHERE l.lead_id = %s AND (l.created_by = %s OR l.assigned_to = %s OR LOWER(l.current_approval_level) = %s)
            ''', (lead_id, user['user_id'], user['user_id'], user['role'].lower()))
        else:
            cursor.execute('''
            SELECT l.*, u1.full_name as created_by_name, u2.full_name as assigned_to_name
            FROM leads l LEFT JOIN users u1 ON l.created_by = u1.id LEFT JOIN users u2 ON l.assigned_to = u2.id
            WHERE l.lead_id = %s
            ''', (lead_id,))
        lead = cursor.fetchone()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        cursor.execute('''SELECT la.*, u.full_name as performed_by_name FROM lead_activities la
                          LEFT JOIN users u ON la.performed_by = u.id WHERE la.lead_id = %s ORDER BY la.activity_date DESC''', (lead_id,))
        activities = cursor.fetchall()

        cursor.execute('''SELECT lsh.*, u.full_name as changed_by_name FROM lead_status_history lsh
                          LEFT JOIN users u ON lsh.changed_by = u.id WHERE lsh.lead_id = %s ORDER BY lsh.changed_at DESC''', (lead_id,))
        status_history = cursor.fetchall()

        cursor.execute('''SELECT lh.*, u.full_name as changed_by_name FROM lead_history lh
                          LEFT JOIN users u ON lh.changed_by = u.id WHERE lh.lead_id = %s ORDER BY lh.changed_at DESC''', (lead_id,))
        field_history = cursor.fetchall()

        lead_dict = dict(lead)
        for ts_field in ("created_at", "updated_at"):
            val = lead_dict.get(ts_field)
            if isinstance(val, str) and val:
                try:
                    lead_dict[ts_field] = datetime.strptime(val, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).isoformat()
                except Exception:
                    pass
        ld = lead_dict.get("created_at") or lead_dict.get("lead_date")
        if ld:
            try:
                date_str = str(ld).split("T")[0].split(" ")[0]
                lead_dict["lead_aging"] = max(0, (date.today() - datetime.strptime(date_str, "%Y-%m-%d").date()).days)
            except Exception:
                pass
        if not lead_dict.get("lead_percentage"):
            lead_dict["lead_percentage"] = calculate_lead_percentage(lead_dict.get("lead_status", "New"))

        def normalize_ts_list(items, field="activity_date"):
            result = [dict(i) for i in items] if items else []
            for item in result:
                val = item.get(field)
                if isinstance(val, str) and val:
                    try:
                        item[field] = datetime.strptime(val, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).isoformat()
                    except Exception:
                        pass
            return result

        return {
            "success": True, "lead": lead_dict,
            "activities": normalize_ts_list(activities, "activity_date"),
            "status_history": normalize_ts_list(status_history, "changed_at"),
            "field_history": normalize_ts_list(field_history, "changed_at")
        }

@app.post("/api/leads")
async def create_lead(lead_data: LeadCreate, user: dict = Depends(get_current_user)):
    if not check_user_permission(user, 'can_create_leads'):
        raise HTTPException(status_code=403, detail="No permission to create leads")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        lead_id = generate_lead_id()
        try:
            lead_date_obj = datetime.strptime(lead_data.lead_date, '%Y-%m-%d').date()
            lead_aging = max(0, (date.today() - lead_date_obj).days)
            assigned_to_id = lead_data.assigned_to if lead_data.assigned_to else user['user_id']
            cursor.execute('SELECT id, full_name FROM users WHERE id = %s', (assigned_to_id,))
            assigned_user = cursor.fetchone()
            if not assigned_user:
                raise HTTPException(status_code=400, detail="Assigned user not found")
            lead_owner_value = lead_data.lead_owner or assigned_user['full_name'] or user['full_name']
            status_value = lead_data.lead_status or 'New'
            lead_percentage = calculate_lead_percentage(status_value)

            cursor.execute('''
            INSERT INTO leads (
                `lead_id`, `lead_date`, `lead_source`, `lead_type`, `lead_owner`,
                `staff_location`, `designation`, `company_name`, `industry_type`, `system`, `project_amc`,
                `state`, `district`, `city`, `pin_code`, `full_address`, `company_website`,
                `company_linkedin_link`, `sub_industry`, `gstin`, `customer_name`,
                `contact_no`, `landline_no`, `email_id`, `linkedin_profile`, `designation_customer`,
                `method_of_communication`, `lead_status`, `lead_aging`, `lead_percentage`,
                `lead_closer_date`, `created_by`, `assigned_to`
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ''', (
                lead_id, lead_data.lead_date, lead_data.lead_source, lead_data.lead_type,
                lead_owner_value, lead_data.staff_location, lead_data.designation, lead_data.company_name,
                lead_data.industry_type, lead_data.system, lead_data.project_amc, lead_data.state,
                lead_data.district, lead_data.city, lead_data.pin_code, lead_data.full_address,
                lead_data.company_website, lead_data.company_linkedin_link, lead_data.sub_industry,
                lead_data.gstin, lead_data.customer_name, lead_data.contact_no, lead_data.landline_no,
                lead_data.email_id, lead_data.linkedin_profile, lead_data.designation_customer,
                lead_data.method_of_communication or 'Email', status_value, lead_aging, lead_percentage,
                lead_data.lead_closer_date, user['user_id'], assigned_to_id
            ))

            cursor.execute('SELECT l.*, u.full_name as created_by_name FROM leads l LEFT JOIN users u ON l.created_by = u.id WHERE l.lead_id = %s', (lead_id,))
            new_lead = cursor.fetchone()

            for field, value in lead_data.dict(exclude_unset=True).items():
                if value is not None and value != '':
                    try:
                        cursor.execute('INSERT INTO lead_history (lead_id, field_name, old_value, new_value, changed_by) VALUES (%s,%s,%s,%s,%s)',
                                       (lead_id, field, None, str(value), user['user_id']))
                    except Exception as e:
                        print(f"History insert error for {field}: {e}")
                        raise

            cursor.execute('INSERT INTO lead_status_history (lead_id, old_status, new_status, changed_by) VALUES (%s,%s,%s,%s)',
                           (lead_id, 'New', status_value, user['user_id']))
            cursor.execute('INSERT INTO lead_activities (lead_id, activity_type, description, performed_by) VALUES (%s,%s,%s,%s)',
                           (lead_id, 'created', f'Lead created: {lead_data.company_name} - {lead_data.customer_name}', user['user_id']))
            conn.commit()
            return {"success": True, "lead_id": lead_id, "lead": dict(new_lead) if new_lead else None, "message": "Lead created successfully"}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/leads/{lead_id}")
async def update_lead(lead_id: str, lead_data: LeadUpdate, user: dict = Depends(get_current_user)):
    if not check_user_permission(user, 'can_edit_leads'):
        raise HTTPException(status_code=403, detail="No permission to edit leads")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM leads WHERE lead_id = %s", (lead_id,))
            current_lead = cursor.fetchone()
            if not current_lead:
                raise HTTPException(status_code=404, detail="Lead not found")

            current_lead_dict = dict(current_lead)
            old_status = current_lead_dict.get("lead_status")

            if (user['role'] != 'admin'
                    and current_lead_dict.get('created_by') != user['user_id']
                    and current_lead_dict.get('assigned_to') != user['user_id']):
                raise HTTPException(status_code=403, detail="No permission to edit this lead")

            reserved = {"system", "state", "order", "group", "user", "key", "date", "percent", "rank"}
            update_fields = []
            params = []
            activity_details = []
            data = lead_data.dict(exclude_unset=True)

            for field, value in data.items():
                if field == "lead_status":
                    continue
                sql_field = f"`{field}`" if field in reserved else field
                old_value = current_lead_dict.get(field)

                if value == "" or value is None:
                    if old_value not in (None, ""):
                        update_fields.append(f"{sql_field} = NULL")
                        cursor.execute('INSERT INTO lead_history (lead_id, field_name, old_value, new_value, changed_by) VALUES (%s,%s,%s,%s,%s)',
                                       (lead_id, field, str(old_value), None, user['user_id']))
                        activity_details.append(f"{field}: '{old_value}' -> (cleared)")
                elif str(value) != str(old_value):
                    update_fields.append(f"{sql_field} = %s")
                    params.append(value)
                    cursor.execute('INSERT INTO lead_history (lead_id, field_name, old_value, new_value, changed_by) VALUES (%s,%s,%s,%s,%s)',
                                   (lead_id, field, str(old_value) if old_value else None, str(value), user['user_id']))
                    activity_details.append(f"{field}: '{old_value}' -> '{value}'")

            # ========== STATUS CHANGE HANDLING ==========
            if lead_data.lead_status is not None and lead_data.lead_status != old_status:
                update_fields.append("lead_status = %s")
                params.append(lead_data.lead_status)

                cursor.execute('INSERT INTO lead_status_history (lead_id, old_status, new_status, changed_by) VALUES (%s,%s,%s,%s)',
                               (lead_id, old_status, lead_data.lead_status, user['user_id']))

                new_percentage = calculate_lead_percentage(lead_data.lead_status)
                if new_percentage:
                    update_fields.append("lead_percentage = %s")
                    params.append(new_percentage)

                # ✅ KICKOFF — set approval tracking + send emails to ALL 4 roles
                normalized_status = lead_data.lead_status.replace(" ", "").upper()
                if normalized_status in ("KICKOFF", "KICK-OFF", "KICK OFF"):
                    update_fields.extend([
                        "approval_status = %s",
                        "current_approval_level = %s",
                        "procurement_allowed = %s",
                    ])
                    params.extend(["PENDING", "oops", 0])

                    # ✅ Send emails to all 4 approver roles immediately
                    try:
                        send_kickoff_emails(lead_id, cursor)
                        print(f"✅ Kickoff emails dispatched for lead {lead_id}")
                    except Exception as email_err:
                        # Non-fatal: log but do not block the status update
                        print(f"⚠️ Kickoff email dispatch error (non-fatal): {email_err}")

                # WON — set approval pending for sales_manager
                elif lead_data.lead_status.upper() == "WON":
                    update_fields.extend([
                        "approval_status = %s",
                        "current_approval_level = %s",
                        "procurement_allowed = %s",
                    ])
                    params.extend(["Pending", "sales_manager", 0])

            # Auto close date when percentage = 100
            final_percentage = lead_data.lead_percentage or (calculate_lead_percentage(lead_data.lead_status) if lead_data.lead_status else current_lead_dict.get("lead_percentage"))
            if int(final_percentage or 0) == 100 and not current_lead_dict.get("lead_closer_date"):
                today = date.today().isoformat()
                update_fields.append("lead_closer_date = %s")
                params.append(today)
                activity_details.append(f"lead_closer_date -> '{today}'")

            if not update_fields:
                return {"success": True, "message": "Nothing to update"}

            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.append(lead_id)
            cursor.execute(f"UPDATE leads SET {', '.join(update_fields)} WHERE lead_id = %s", params)

            for detail in activity_details:
                field_name = detail.split(":")[0]
                readable = field_name.replace("_", " ").title()
                desc = f"Cleared {readable}" if "cleared" in detail else f"Updated {readable}"
                cursor.execute('INSERT INTO lead_activities (lead_id, activity_type, description, performed_by) VALUES (%s,%s,%s,%s)',
                               (lead_id, "field_update", desc, user['user_id']))

            conn.commit()
            return {"success": True, "message": "Lead updated successfully"}

        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/leads/{lead_id}")
async def delete_lead(lead_id: str, user: dict = Depends(get_current_user)):
    if not check_user_permission(user, 'can_delete_leads'):
        raise HTTPException(status_code=403, detail="No permission to delete leads")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM leads WHERE lead_id = %s', (lead_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Lead not found")
            cursor.execute('DELETE FROM lead_history WHERE lead_id = %s', (lead_id,))
            cursor.execute('DELETE FROM lead_status_history WHERE lead_id = %s', (lead_id,))
            cursor.execute('DELETE FROM lead_activities WHERE lead_id = %s', (lead_id,))
            cursor.execute('DELETE FROM leads WHERE lead_id = %s', (lead_id,))
            conn.commit()
            return {"success": True, "message": "Lead and all related data deleted successfully"}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/settings/lead-settings")
async def get_lead_settings_api(user: dict = Depends(get_current_user)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT setting_type, setting_data FROM lead_settings')
        rows = cursor.fetchall()
        settings = {}
        for row in rows:
            try:
                settings[row['setting_type']] = json.loads(row['setting_data'])
            except Exception:
                settings[row['setting_type']] = []
        return {"success": True, "settings": settings}

@app.post("/api/settings/lead-settings")
async def save_lead_settings_api(request: Request, user: dict = Depends(get_current_user)):
    if not check_user_permission(user, 'can_manage_users') and user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="No permission to save settings")
    try:
        data = await request.json()
        setting_type = data.get('type') or "lead_statuses"
        setting_data = data.get('data') or data.get('lead_statuses') or []
        if not setting_type:
            raise HTTPException(status_code=400, detail="Setting type is required")
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM lead_settings WHERE setting_type = %s', (setting_type,))
            existing = cursor.fetchone()
            setting_json = json.dumps(setting_data)
            if existing:
                cursor.execute('UPDATE lead_settings SET setting_data = %s, updated_at = CURRENT_TIMESTAMP, updated_by = %s WHERE setting_type = %s',
                               (setting_json, user['user_id'], setting_type))
            else:
                cursor.execute('INSERT INTO lead_settings (setting_type, setting_data, updated_by) VALUES (%s, %s, %s)',
                               (setting_type, setting_json, user['user_id']))
            conn.commit()
            return {"success": True, "message": f"{setting_type} settings saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/stats")
async def get_dashboard_stats(user: dict = Depends(get_current_user)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        where_clause = ""
        params = []
        if user['role'] != 'admin':
            where_clause = "WHERE (created_by = %s OR assigned_to = %s)"
            params = [user['user_id'], user['user_id']]
        cursor.execute(f'SELECT COUNT(*) as count FROM leads {where_clause}', params)
        result = cursor.fetchone()
        total_leads = result['count'] if result else 0
        prefs = get_preferences()
        follow_up_days = int(prefs.get('followUpDays', 7))
        cursor.execute(f'SELECT COUNT(*) as count FROM leads WHERE next_follow_up_date >= CURDATE() AND next_follow_up_date <= DATE_ADD(CURDATE(), INTERVAL {follow_up_days} DAY) {where_clause}', params)
        upcoming_followups = (cursor.fetchone() or {}).get('count', 0)
        
        cursor.execute(f'SELECT lead_status, COUNT(*) as count FROM leads {where_clause} GROUP BY lead_status ORDER BY count DESC', params)
        leads_by_status = cursor.fetchall()
        cursor.execute(f'SELECT lead_id, company_name, customer_name, lead_status, updated_at FROM leads {where_clause} ORDER BY updated_at DESC LIMIT 10', params)
        recent_leads = [dict(l) for l in cursor.fetchall()] if cursor.fetchall() else []
        return {"success": True, "stats": {
            "total_leads": total_leads, "upcoming_followups": upcoming_followups,
            "leads_by_status": [dict(s) for s in leads_by_status] if leads_by_status else [],
            "recent_leads": recent_leads
        }}

@app.get("/api/designations")
async def get_designations(user: dict = Depends(get_current_user)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, name FROM designations ORDER BY name')
        designations = cursor.fetchall()
        return {"success": True, "designations": [dict(d) for d in designations]}

@app.post("/api/designations")
async def create_designation(designation_data: dict, current_user: dict = Depends(get_current_user)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO designations (name) VALUES (%s)', (designation_data.get('name'),))
            conn.commit()
            return {"success": True, "id": cursor.lastrowid, "name": designation_data.get('name')}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/user")
async def get_current_user_info(user: dict = Depends(get_current_user)):
    return {"user_id": user["user_id"], "username": user["username"], "full_name": user["full_name"],
            "email": user["email"], "role": user["role"], "permissions": user["permissions"], "is_admin": user['role'] == 'admin'}

@app.get("/api/users")
async def get_all_users(user: dict = Depends(get_current_user)):
    if not check_user_permission(user, 'can_view_users'):
        raise HTTPException(status_code=403, detail="No permission to view users")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''SELECT u.*, uc.full_name as created_by_name FROM users u
                          LEFT JOIN users uc ON u.created_by = uc.id WHERE u.id != %s ORDER BY u.created_at DESC''', (user['user_id'],))
        users_data = cursor.fetchall()
        users_list = [dict(u) for u in users_data] if users_data else []
        for usr in users_list:
            cursor.execute('SELECT COUNT(*) as count FROM user_permissions WHERE user_id = %s AND granted = 1', (usr['id'],))
            count_result = cursor.fetchone()
            usr['permission_count'] = count_result['count'] if count_result else 0
        return {"success": True, "users": users_list}

@app.post("/api/users")
async def create_user(user_data: UserCreate, current_user: dict = Depends(get_current_user)):
    if not check_user_permission(current_user, 'can_manage_users'):
        raise HTTPException(status_code=403, detail="No permission to manage users")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE username = %s', (user_data.username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username already exists")
        if not user_data.permissions:
            default_perms = {'admin': UserPermissions().dict(), 'sales': UserPermissions(can_view_users=False, can_manage_users=False, can_delete_leads=False).dict()}
            permissions = default_perms.get(user_data.role.value, UserPermissions().dict())
        else:
            permissions = user_data.permissions
        try:
            cursor.execute('''INSERT INTO users (username, password, first_name, last_name, full_name, email, designation, mobile_no, date_of_birth, photo, role, permissions, created_by)
                              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                           (user_data.username, hash_password(user_data.password), user_data.first_name, user_data.last_name,
                            user_data.full_name, user_data.email, user_data.designation, user_data.mobile_no,
                            user_data.date_of_birth, user_data.photo, user_data.role.value, json.dumps(permissions), current_user['user_id']))
            conn.commit()
            return {"success": True, "message": "User created successfully"}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users/active")
async def get_active_users(user: dict = Depends(get_current_user)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, full_name, role, designation, email, mobile_no FROM users WHERE is_active = 1 ORDER BY full_name')
        users = cursor.fetchall()
        return {"success": True, "users": [dict(u) for u in users] if users else []}

@app.post("/api/upload/photo")
async def upload_photo(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    if not check_user_permission(current_user, 'can_manage_users'):
        raise HTTPException(status_code=403, detail="No permission")
    try:
        upload_dir = os.path.join("static", "uploads", "users")
        os.makedirs(upload_dir, exist_ok=True)
        _, ext = os.path.splitext(file.filename or '')
        ext = ext.lower()
        if ext not in {'.jpg', '.jpeg', '.png', '.gif', '.webp'}:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        filename = f"{uuid.uuid4().hex}{ext}"
        with open(os.path.join(upload_dir, filename), 'wb') as out_file:
            shutil.copyfileobj(file.file, out_file)
        return {"success": True, "path": f"uploads/users/{filename}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/users/{user_id}")
async def update_user(user_id: int, user_data: dict, current_user: dict = Depends(get_current_user)):
    if not check_user_permission(current_user, 'can_manage_users'):
        raise HTTPException(status_code=403, detail="No permission to manage users")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE id = %s', (user_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")
        try:
            fields = []
            values = []
            field_map = ['first_name','last_name','full_name','email','designation','mobile_no','date_of_birth','photo','role']
            for f in field_map:
                if f in user_data:
                    fields.append(f'{f} = %s')
                    values.append(user_data[f])
            if 'password' in user_data:
                fields.append('password = %s')
                values.append(hash_password(user_data['password']))
            if not fields:
                raise HTTPException(status_code=400, detail="No fields to update")
            values.append(user_id)
            cursor.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = %s", values)
            conn.commit()
            return {"success": True, "message": "User updated successfully"}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/users/{user_id}/permissions")
async def update_user_permissions(user_id: int, permissions_data: dict, current_user: dict = Depends(get_current_user)):
    if not check_user_permission(current_user, 'can_manage_users'):
        raise HTTPException(status_code=403, detail="No permission to manage users")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE id = %s', (user_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")
        try:
            cursor.execute('UPDATE users SET permissions = %s WHERE id = %s', (json.dumps(permissions_data.get('permissions', {})), user_id))
            conn.commit()
            return {"success": True, "message": "Permissions updated successfully"}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/users/{user_id}/status")
async def update_user_status(user_id: int, status_data: dict, current_user: dict = Depends(get_current_user)):
    if not check_user_permission(current_user, 'can_manage_users'):
        raise HTTPException(status_code=403, detail="No permission to manage users")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE id = %s', (user_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")
        try:
            is_active = status_data.get('is_active', True)
            cursor.execute('UPDATE users SET is_active = %s WHERE id = %s', (is_active, user_id))
            conn.commit()
            return {"success": True, "message": f"User {'activated' if is_active else 'deactivated'} successfully"}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/users/{user_id}")
async def delete_user(user_id: int, current_user: dict = Depends(get_current_user)):
    if not check_user_permission(current_user, 'can_manage_users'):
        raise HTTPException(status_code=403, detail="No permission to manage users")
    if current_user['user_id'] == user_id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, is_active FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user['is_active'] == 0:
            raise HTTPException(status_code=400, detail="User already deactivated")
        try:
            cursor.execute("UPDATE users SET is_active = 0 WHERE id = %s", (user_id,))
            conn.commit()
            return {"success": True, "message": "User deactivated successfully"}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/users/{user_id}/activate")
async def activate_user(user_id: int, current_user: dict = Depends(get_current_user)):
    if not check_user_permission(current_user, 'can_manage_users'):
        raise HTTPException(status_code=403, detail="No permission to manage users")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, is_active FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user['is_active'] == 1:
            raise HTTPException(status_code=400, detail="User already active")
        try:
            cursor.execute("UPDATE users SET is_active = 1 WHERE id = %s", (user_id,))
            conn.commit()
            return {"success": True, "message": "User activated successfully"}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))


# ============ TARGETS ============

@app.get("/api/targets")
async def get_targets(user: dict = Depends(get_current_user)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM targets WHERE is_active = 1 ORDER BY created_at DESC')
        targets = cursor.fetchall()
        return {"success": True, "targets": [dict(t) for t in targets] if targets else []}

@app.post("/api/targets")
async def create_target(request: Request, user: dict = Depends(get_current_user)):
    try:
        data = await request.json()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO targets (name, type, target_value, current_value, assigned_to, period, context_tab, description, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                           (data.get('name'), data.get('type'), data.get('target_value', 0), data.get('current_value', 0),
                            data.get('assigned_to', user['user_id']), data.get('period'), data.get('context_tab'), data.get('description', ''), user['user_id']))
            conn.commit()
            return {"success": True, "message": "Target created successfully", "target_id": cursor.lastrowid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/targets/{target_id}")
async def update_target(target_id: int, request: Request, user: dict = Depends(get_current_user)):
    try:
        data = await request.json()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            fields = []
            params = []
            for field in ['name','type','target_value','current_value','period','context_tab','description']:
                if field in data:
                    fields.append(f'{field} = %s')
                    params.append(data[field])
            fields.append('updated_at = CURRENT_TIMESTAMP')
            params.append(target_id)
            cursor.execute(f"UPDATE targets SET {', '.join(fields)} WHERE id = %s", params)
            conn.commit()
            return {"success": True, "message": "Target updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/targets/{target_id}")
async def delete_target(target_id: int, user: dict = Depends(get_current_user)):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE targets SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s', (target_id,))
            conn.commit()
            return {"success": True, "message": "Target deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ AUDIT LOGS ============

@app.get("/api/audit/logs")
async def get_audit_logs(
    request: Request, user: dict = Depends(get_current_user),
    user_id: Optional[int] = None, action: Optional[str] = None,
    resource_type: Optional[str] = None, date_from: Optional[str] = None,
    date_to: Optional[str] = None, page: int = 1, limit: int = 50,
):
    if user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        where = []
        params = []
        if user_id is not None:
            where.append('user_id = %s'); params.append(user_id)
        if action:
            where.append('action = %s'); params.append(action)
        if resource_type:
            where.append('resource_type = %s'); params.append(resource_type)
        if date_from:
            where.append("DATE(created_at) >= DATE(%s)"); params.append(date_from)
        if date_to:
            where.append("DATE(created_at) <= DATE(%s)"); params.append(date_to)
        base = 'SELECT * FROM audit_logs' + (' WHERE ' + ' AND '.join(where) if where else '')
        cursor.execute('SELECT COUNT(*) as count FROM (' + base + ') AS c', params)
        total = (cursor.fetchone() or {}).get('count', 0)
        cursor.execute(base + ' ORDER BY created_at DESC LIMIT %s OFFSET %s', params + [limit, (page - 1) * limit])
        rows = cursor.fetchall()
        return {"success": True, "data": [dict(r) for r in rows] if rows else [],
                "pagination": {"page": page, "limit": limit, "total": total, "pages": (total + limit - 1) // limit if limit > 0 else 0}}


# ============ PERMISSIONS ============

@app.get("/api/permissions")
async def get_all_permissions(user: dict = Depends(get_current_user)):
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Only admins can view all permissions")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, permission_key, permission_name, parent_id, category, level, description FROM permissions ORDER BY level, parent_id, permission_key')
        rows = cursor.fetchall()
        return {"success": True, "data": [dict(r) for r in rows] if rows else []}

@app.get("/api/permissions/tree")
async def get_permissions_tree(user: dict = Depends(get_current_user)):
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Only admins can view permission tree")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, permission_key, permission_name, parent_id, category, level, description FROM permissions ORDER BY level, parent_id, permission_key')
        all_perms = [dict(r) for r in cursor.fetchall()]
        tree = []
        perm_map = {p['id']: {**p, 'children': []} for p in all_perms}
        for perm in all_perms:
            if perm['parent_id'] is None:
                tree.append(perm_map[perm['id']])
            elif perm['parent_id'] in perm_map:
                perm_map[perm['parent_id']]['children'].append(perm_map[perm['id']])
        return {"success": True, "data": tree}

@app.get("/api/users/{user_id}/permissions")
async def get_user_permissions(user_id: int, user: dict = Depends(get_current_user)):
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Only admins can view user permissions")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, full_name, role FROM users WHERE id = %s', (user_id,))
        user_data = cursor.fetchone()
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        cursor.execute('''SELECT p.id, p.permission_key, p.permission_name, p.parent_id, p.category, p.level, up.granted, up.granted_at
                          FROM user_permissions up JOIN permissions p ON up.permission_id = p.id
                          WHERE up.user_id = %s AND up.granted = 1 ORDER BY p.level, p.permission_key''', (user_id,))
        permissions = [dict(r) for r in cursor.fetchall()]
        return {"success": True, "user": dict(user_data), "permissions": permissions,
                "permission_keys": [p['permission_key'] for p in permissions]}

@app.post("/api/users/{user_id}/permissions")
async def assign_user_permissions(user_id: int, request: Request, user: dict = Depends(get_current_user)):
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Only admins can assign permissions")
    try:
        data = await request.json()
        permission_ids = data.get('permission_ids', [])
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM users WHERE id = %s', (user_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="User not found")
            cursor.execute('DELETE FROM user_permissions WHERE user_id = %s', (user_id,))
            for perm_id in permission_ids:
                cursor.execute('INSERT INTO user_permissions (user_id, permission_id, granted, granted_by) VALUES (%s,%s,1,%s)',
                               (user_id, perm_id, user['user_id']))
            conn.commit()
            return {"success": True, "message": f"Assigned {len(permission_ids)} permissions"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/users/{user_id}/permissions/{permission_id}")
async def revoke_user_permission(user_id: int, permission_id: int, request: Request, user: dict = Depends(get_current_user)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM user_permissions WHERE user_id = %s AND permission_id = %s', (user_id, permission_id))
        conn.commit()
        return {"success": True, "message": "Permission revoked"}

@app.post("/api/check-permission")
async def check_permission(request: Request, user: dict = Depends(get_current_user)):
    try:
        data = await request.json()
        permission_key = data.get('permission_key')
        if not permission_key:
            raise HTTPException(status_code=400, detail="permission_key required")
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''SELECT COUNT(*) as count FROM user_permissions up
                              JOIN permissions p ON up.permission_id = p.id
                              WHERE up.user_id = %s AND p.permission_key = %s AND up.granted = 1''', (user['user_id'], permission_key))
            result = cursor.fetchone()
            return {"success": True, "has_permission": result['count'] > 0 if result else False}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ APPROVAL ENDPOINTS ============

@app.get("/api/leads/pending-approvals")
async def pending_approvals(user: dict = Depends(get_current_user)):
    """
    Returns leads pending approval for the current user's role.
    Roles in the approval chain: oops → finance → admin → scm
    """
    role = (user.get("role") or "").lower().strip()
    allowed_roles = ["oops", "finance", "admin", "scm"]

    if role not in allowed_roles:
        return {"success": True, "leads": []}

    with get_db_connection() as conn:
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("""
            SELECT *
            FROM leads
            WHERE LOWER(approval_status) = 'pending'
            AND LOWER(current_approval_level) = %s
        """, (role,))
        leads = cursor.fetchall()

    return {"success": True, "leads": leads if leads else []}


@app.post("/api/leads/{lead_id}/approve")
async def approve_lead(
    lead_id: str,
    payload: LeadApprovalPayload,
    user: dict = Depends(get_current_user)
):
    """
    Multi-level approval: oops → finance → admin → scm
    All 4 approved  → lead marked as Won, procurement_allowed = 1
    Any rejected    → lead marked Rejected
    """
    try:
        action = (payload.action or "").upper()
        role = (user.get("role") or "").lower().strip()
        comment = (payload.comment or "").strip()

        if action not in ["APPROVE", "REJECT"]:
            raise HTTPException(status_code=400, detail="Invalid action. Use APPROVE or REJECT.")

        # String-based sequence
        role_sequence = ["oops", "finance", "admin", "scm"]

        if role not in role_sequence:
            raise HTTPException(status_code=403, detail=f"Role '{role}' is not an approval role.")

        with get_db_connection() as conn:
            cursor = conn.cursor(pymysql.cursors.DictCursor)

            cursor.execute("SELECT * FROM leads WHERE lead_id = %s", (lead_id,))
            lead = cursor.fetchone()

            if not lead:
                raise HTTPException(status_code=404, detail="Lead not found")

            lead_db_id = lead["id"]
            current_level = (lead.get("current_approval_level") or "").lower().strip()

            if current_level != role:
                raise HTTPException(
                    status_code=403,
                    detail=f"This lead requires approval from '{current_level.upper()}', not '{role.upper()}'"
                )

            # Check if this role already approved
            cursor.execute("""
                SELECT id FROM lead_approvals
                WHERE lead_id = %s AND LOWER(approval_level) = %s AND action = 'APPROVE'
            """, (lead_db_id, role))

            if cursor.fetchone():
                raise HTTPException(status_code=400, detail=f"'{role.upper()}' has already approved this lead.")

            # Insert approval record
            cursor.execute("""
                INSERT INTO lead_approvals (lead_id, approval_level, action, comment, approved_by)
                VALUES (%s, %s, %s, %s, %s)
            """, (lead_db_id, role, action, comment, user["user_id"]))

            # ===== REJECTED =====
            if action == "REJECT":
                cursor.execute("""
                    UPDATE leads SET approval_status = 'Rejected', procurement_allowed = 0
                    WHERE lead_id = %s
                """, (lead_id,))
                cursor.execute(
                    'INSERT INTO lead_activities (lead_id, activity_type, description, performed_by) VALUES (%s,%s,%s,%s)',
                    (lead_id, 'status_change', f'Approval rejected by {role.upper()}', user['user_id'])
                )
                conn.commit()
                return {"success": True, "message": f"Lead rejected by {role.upper()}"}

            # ===== APPROVED — move to next level =====
            current_idx = role_sequence.index(role)
            if current_idx + 1 < len(role_sequence):
                next_level = role_sequence[current_idx + 1]
                cursor.execute("""
                    UPDATE leads SET current_approval_level = %s WHERE lead_id = %s
                """, (next_level, lead_id))
                print(f"✅ Approval by {role} done. Next level: {next_level}")
            else:
                print(f"✅ {role} is the last approver")

            # Count total unique approvals across all 4 levels
            cursor.execute("""
                SELECT COUNT(DISTINCT LOWER(approval_level)) as total
                FROM lead_approvals
                WHERE lead_id = %s AND action = 'APPROVE'
                AND LOWER(approval_level) IN ('oops', 'finance', 'admin', 'scm')
            """, (lead_db_id,))

            result = cursor.fetchone()
            total_approved = result["total"] if result else 0
            print(f"Total approvals so far: {total_approved}")

            # ===== ALL 4 APPROVED — MARK WON =====
            if total_approved >= 4:
                cursor.execute("""
                    UPDATE leads
                    SET lead_status = 'Won', approval_status = 'Approved', procurement_allowed = 1
                    WHERE lead_id = %s
                """, (lead_id,))
                print(f"✅ Lead {lead_id} marked as WON after all 4 approvals")

            # Log activity
            cursor.execute(
                'INSERT INTO lead_activities (lead_id, activity_type, description, performed_by) VALUES (%s,%s,%s,%s)',
                (lead_id, 'status_change', f'Approved by {role.upper()}. Comment: {comment}', user['user_id'])
            )
            conn.commit()

        return {"success": True, "message": f"Approved successfully by {role.upper()}"}

    except HTTPException:
        raise
    except Exception as e:
        print("Approval ERROR:", e)
        raise HTTPException(status_code=500, detail=f"Approval failed: {str(e)}")

import random
import string

# In-memory store for reset tokens (valid for 15 min)
password_reset_tokens = {}

@app.post("/api/forgot-password")
async def forgot_password(request: Request):
    try:
        data = await request.json()
        email = (data.get('email') or '').strip()
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, full_name, email FROM users WHERE email = %s AND is_active = 1", (email,))
            user = cursor.fetchone()

        if not user:
            # Don't reveal if email exists
            return {"success": True, "message": "If this email exists, a reset link has been sent."}

        # Generate 6-digit OTP
        otp = ''.join(random.choices(string.digits, k=6))
        expires_at = datetime.now() + timedelta(minutes=15)
        password_reset_tokens[email] = {"otp": otp, "user_id": user['id'], "expires_at": expires_at}

        # Send email
        body = f"""
        <div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:20px;">
            <div style="background:#0d6efd;padding:20px;border-radius:10px 10px 0 0;text-align:center;">
                <h2 style="color:white;margin:0;">Password Reset</h2>
            </div>
            <div style="background:#f8f9fa;padding:30px;border-radius:0 0 10px 10px;border:1px solid #dee2e6;">
                <p>Dear <b>{user['full_name']}</b>,</p>
                <p>Your password reset OTP is:</p>
                <div style="text-align:center;margin:25px 0;">
                    <span style="font-size:36px;font-weight:700;letter-spacing:10px;color:#0d6efd;
                        background:white;padding:15px 25px;border-radius:8px;border:2px solid #0d6efd;">
                        {otp}
                    </span>
                </div>
                <p style="color:#dc2626;"><b>This OTP is valid for 15 minutes only.</b></p>
                <p style="color:#6c757d;font-size:0.9em;">If you did not request this, please ignore this email.</p>
                <hr style="border:none;border-top:1px solid #dee2e6;margin:20px 0;">
                <p style="color:#6c757d;font-size:0.85em;text-align:center;">
                    Smart CRM — Cogent Safety & Security Pvt Ltd
                </p>
            </div>
        </div>
        """
        send_email(email, "Password Reset OTP - Smart CRM", body)
        return {"success": True, "message": "OTP sent to your email address."}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/reset-password")
async def reset_password(request: Request):
    try:
        data = await request.json()
        email = (data.get('email') or '').strip()
        otp = (data.get('otp') or '').strip()
        new_password = (data.get('new_password') or '').strip()

        if not all([email, otp, new_password]):
            raise HTTPException(status_code=400, detail="All fields are required")

        if len(new_password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

        token_data = password_reset_tokens.get(email)
        if not token_data:
            raise HTTPException(status_code=400, detail="Invalid or expired OTP")

        if datetime.now() > token_data['expires_at']:
            del password_reset_tokens[email]
            raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")

        if token_data['otp'] != otp:
            raise HTTPException(status_code=400, detail="Invalid OTP")

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET password = %s WHERE id = %s",
                           (hash_password(new_password), token_data['user_id']))
            conn.commit()

        del password_reset_tokens[email]
        return {"success": True, "message": "Password reset successfully. Please login with your new password."}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)