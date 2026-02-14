import streamlit as st
from dataclasses import dataclass
from typing import List, Dict, Any
import time
from datetime import datetime, timedelta

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import JsonOutputParser

# =========================
# ORCHESTRATOR IMPORT
# =========================
try:
    from orchestrator import (
        ProcurementOrchestrator,
        WorkflowContext,
        WorkflowStatus,
        AgentStatus
    )
    ORCHESTRATOR_AVAILABLE = True
except ImportError:
    ORCHESTRATOR_AVAILABLE = False
    print("⚠️ Orchestrator module not found")


# =========================
# LLM
# =========================
@st.cache_resource
def get_llm():
    return ChatOllama(model="qwen2.5:3b", temperature=0)


llm = get_llm()


# =========================
# MODELS
# =========================
@dataclass
class Email:
    id: int
    sender: str
    subject: str
    body: str
    category: str
    priority: str


@dataclass
class PurchaseRequest:
    item: str
    quantity: int
    budget: float


@dataclass
class Supplier:
    name: str
    price_per_unit: float
    compliant: bool


# =========================
# MOCK DATA
# =========================
MOCK_EMAILS = [
    Email(
        id=1,
        sender="Cassie Matthews",
        subject="Urgent: Branded Water Bottles Needed",
        body="Hi, we need 300 branded water bottles for the upcoming conference. Budget is 15000 TL. Please process ASAP.",
        category="Procurement Request",
        priority="High"
    ),
    Email(
        id=2,
        sender="John Smith",
        subject="Office Supplies Request",
        body="Please order 50 notebooks and 100 pens. Budget: 2000 TL.",
        category="Procurement Request",
        priority="Medium"
    ),
    Email(
        id=3,
        sender="Sarah Connor",
        subject="Meeting Room Update",
        body="The meeting room schedule has been updated.",
        category="General",
        priority="Low"
    ),
    Email(
        id=4,
        sender="Mike Johnson",
        subject="Laptop Purchase Request",
        body="Need 10 laptops for new employees. Budget is 80000 TL.",
        category="Procurement Request",
        priority="High"
    ),
]


# =========================
# PROMPTS
# =========================
email_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Extract purchase request from email. Return JSON with: item, quantity, budget.\n"
     "Example: {{\"item\": \"laptop\", \"quantity\": 5, \"budget\": 50000.0}}"),
    ("human", "{email}")
])

approval_prompt = ChatPromptTemplate.from_messages([
    ("system", "Create approval email. Return JSON: subject, body, manager_email."),
    ("human",
     "Item: {item}\nQuantity: {quantity}\nSupplier: {supplier}\n"
     "Total: {total} TL\nBudget: {budget} TL\nReason: {reason}")
])


# =========================
# HELPER FUNCTIONS
# =========================
def add_history(action: str, details: str, status: str = "success"):
    """Add event to history with timestamp"""
    st.session_state.history.append({
        'timestamp': datetime.now().strftime("%H:%M:%S"),
        'action': action,
        'details': details,
        'status': status
    })


def schedule_reminder(manager_email: str, subject: str, interval_minutes: int):
    """Simulate scheduling an email reminder"""
    reminder_time = datetime.now() + timedelta(minutes=interval_minutes)
    return {
        'to': manager_email,
        'subject': f"REMINDER: {subject}",
        'scheduled_time': reminder_time.strftime("%H:%M:%S"),
        'interval': f"{interval_minutes} minutes",
        'status': 'scheduled'
    }


# =========================
# AGENT FUNCTIONS (Core Logic)
# =========================
def run_email_agent(email_body: str) -> PurchaseRequest:
    chain = email_prompt | llm | JsonOutputParser()
    data = chain.invoke({"email": email_body})
    return PurchaseRequest(
        item=data["item"],
        quantity=int(data["quantity"]),
        budget=float(data["budget"])
    )


def run_supplier_agent(request: PurchaseRequest) -> List[Supplier]:
    import random
    base_price = request.budget / request.quantity
    suppliers = []
    for i in range(3):
        price_variation = random.uniform(0.8, 1.3)
        suppliers.append(Supplier(
            name=f"Supplier_{chr(65+i)}",
            price_per_unit=round(base_price * price_variation, 2),
            compliant=random.choice([True, True, True, False])
        ))
    return suppliers


def run_compliance_agent(supplier: Supplier, request: PurchaseRequest) -> tuple:
    total_cost = supplier.price_per_unit * request.quantity
    if not supplier.compliant:
        return False, "Supplier is not compliant with company policies"
    if total_cost > request.budget:
        return False, f"Budget exceeded: {total_cost} TL > {request.budget} TL"
    return True, ""


def run_approval_agent(request: PurchaseRequest, supplier: Supplier, reason: str) -> Dict:
    total = supplier.price_per_unit * request.quantity
    chain = approval_prompt | llm | JsonOutputParser()
    return chain.invoke({
        "item": request.item,
        "quantity": request.quantity,
        "supplier": supplier.name,
        "total": total,
        "budget": request.budget,
        "reason": reason
    })


def run_order_agent(request: PurchaseRequest, supplier: Supplier) -> Dict:
    return {
        "supplier": supplier.name,
        "item": request.item,
        "quantity": request.quantity,
        "total_price": supplier.price_per_unit * request.quantity,
        "status": "ORDER_PLACED"
    }


# =========================
# ORCHESTRATOR AGENT WRAPPERS
# =========================
def email_agent_wrapper(context, **kwargs):
    result = run_email_agent(context.email_data.get('body', ''))
    add_history("📨 Email Agent",
                f"Extracted: {result.item} (qty: {result.quantity}, budget: {result.budget} TL)", "success")
    return result


def supplier_agent_wrapper(context, **kwargs):
    result = run_supplier_agent(context.purchase_request)
    add_history("🏭 Supplier Agent",
                f"Found {len(result)} suppliers", "success")
    return result


def compliance_agent_wrapper(context, **kwargs):
    result = run_compliance_agent(
        context.selected_supplier, context.purchase_request)
    is_compliant, reason = result
    status = "success" if is_compliant else "warning"
    add_history("📋 Compliance Agent",
                reason if reason else "All checks passed", status)
    return result


def approval_agent_wrapper(context, **kwargs):
    result = run_approval_agent(
        context.purchase_request,
        context.selected_supplier,
        kwargs.get('reason', 'Approval required')
    )
    add_history("📧 Approval Agent",
                f"Email created: {result.get('subject', 'N/A')}", "success")
    return result


def order_agent_wrapper(context, **kwargs):
    result = run_order_agent(context.purchase_request,
                             context.selected_supplier)
    add_history("🧾 Order Agent",
                f"Order placed: {result['total_price']} TL", "success")
    return result


# =========================
# ORCHESTRATOR INITIALIZATION
# =========================
def initialize_orchestrator():
    """Initialize orchestrator and register all agents"""
    if not ORCHESTRATOR_AVAILABLE:
        return None

    orchestrator = ProcurementOrchestrator()
    orchestrator.register_agent('email_agent', email_agent_wrapper)
    orchestrator.register_agent('supplier_agent', supplier_agent_wrapper)
    orchestrator.register_agent('compliance_agent', compliance_agent_wrapper)
    orchestrator.register_agent('approval_agent', approval_agent_wrapper)
    orchestrator.register_agent('order_agent', order_agent_wrapper)

    return orchestrator


# =========================
# SESSION STATE INIT
# =========================
def init_session_state():
    defaults = {
        'page': 'inbox',
        'selected_email': None,
        'history': [],
        'scheduled_reminders': [],
        'workflow_context': None,
        'approval_sent': False,
        'emails_loaded': False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Orchestrator - sadece bir kez başlat
    if 'orchestrator' not in st.session_state:
        st.session_state.orchestrator = initialize_orchestrator()
        if st.session_state.orchestrator:
            add_history(
                "🤖 System", "Orchestrator initialized - 5 agents registered", "success")


# =========================
# HELPER: Get context data
# =========================
def get_context():
    """MD madde 4: UI Data Binding - tüm veriler context'ten gelir"""
    ctx = st.session_state.workflow_context
    if ctx:
        return ctx
    return None


# =========================
# PAGE: INBOX
# =========================
def page_inbox():
    """MD madde 3: Email Seçildiğinde - Orchestrator.execute_workflow() başlatılır"""
    st.title("🏢 Greypine Procurement Assistant")
    st.markdown("**AI-enabled Supplier Engagement Portal**")
    st.divider()

    st.subheader("📨 Email Management")

    if st.button("📧 Read and classify unread emails in Outlook", type="primary"):
        with st.spinner("Connecting to Outlook and classifying emails..."):
            time.sleep(1)
            st.session_state.emails_loaded = True

    if st.session_state.emails_loaded:
        st.success("✅ Emails classified successfully!")
        st.markdown("### 📋 Category: Procurement Requests")

        procurement_emails = [
            e for e in MOCK_EMAILS if e.category == "Procurement Request"]

        for email in procurement_emails:
            with st.container():
                col1, col2 = st.columns([4, 1])

                with col1:
                    priority_emoji = "🔴" if email.priority == "High" else "🟡" if email.priority == "Medium" else "🟢"
                    st.markdown(f"**{priority_emoji} From:** {email.sender}")
                    st.markdown(f"**Subject:** {email.subject}")

                with col2:
                    if st.button("Select", key=f"select_{email.id}"):

                        # ✅ MD MADDE 3: Orchestrator workflow başlat
                        orchestrator = st.session_state.orchestrator

                        email_data = {
                            'id': email.id,
                            'sender': email.sender,
                            'subject': email.subject,
                            'body': email.body
                        }

                        add_history("📧 Email Selected",
                                    f"From: {email.sender} - {email.subject}")

                        with st.spinner("🤖 Orchestrator: Running Email Agent & Supplier Agent..."):
                            # Execute workflow - pauses at supplier selection (PENDING)
                            context = orchestrator.execute_workflow(email_data)
                            st.session_state.workflow_context = context

                        # ✅ MD MADDE 3: Navigate based on workflow status
                        if context.workflow_status == WorkflowStatus.PENDING:
                            st.session_state.page = 'sourcing'
                        else:
                            st.session_state.page = 'detail'

                        st.rerun()

                st.divider()


# =========================
# PAGE: DETAIL (Legacy fallback)
# =========================
def page_detail():
    st.title("📧 Email Details")

    email = st.session_state.selected_email
    if not email:
        st.warning("No email selected")
        if st.button("← Back to Inbox"):
            st.session_state.page = 'inbox'
            st.rerun()
        return

    if st.button("← Back to Inbox"):
        st.session_state.page = 'inbox'
        st.rerun()

    st.divider()
    st.markdown(f"### From: {email.sender}")
    st.markdown(f"**Subject:** {email.subject}")
    st.info(f"📄 {email.body}")


# =========================
# PAGE: SOURCING
# =========================
def page_sourcing():
    """MD madde 3 & 4: Supplier seçiminde orchestrator.resume_workflow() çağrılır"""
    st.title("🏭 Sourcing Agent - Supplier Selection")

    # ✅ MD MADDE 4: UI Data Binding - context'ten veri al
    ctx = get_context()

    if not ctx:
        st.error("No active workflow. Please select an email first.")
        if st.button("← Back to Inbox"):
            st.session_state.page = 'inbox'
            st.rerun()
        return

    request = ctx.purchase_request
    suppliers = ctx.suppliers

    if st.button("← Back"):
        st.session_state.page = 'inbox'
        st.rerun()

    st.divider()

    # Procurement details from context
    st.markdown("### 📦 Procurement Details")
    col1, col2, col3 = st.columns(3)
    col1.metric("Item", request.item)
    col2.metric("Quantity", request.quantity)
    col3.metric("Budget", f"{request.budget} TL")

    st.divider()

    st.markdown("### 🏢 Available Suppliers")
    st.caption("✨ Suppliers already found by Orchestrator's Sourcing Agent")

    for idx, supplier in enumerate(suppliers):
        total_cost = supplier.price_per_unit * request.quantity
        compliance_badge = "✅ Compliant" if supplier.compliant else "❌ Non-compliant"

        with st.container():
            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
            col1.markdown(f"**{supplier.name}**")
            col2.markdown(f"Unit: {supplier.price_per_unit} TL")
            col3.markdown(f"Total: {total_cost} TL")
            col4.markdown(compliance_badge)

            if col5.button("Select", key=f"supplier_{idx}"):

                # ✅ MD MADDE 3: Resume workflow with supplier selection
                orchestrator = st.session_state.orchestrator

                with st.spinner("🤖 Orchestrator: Running Compliance Agent..."):
                    user_input = {'selected_supplier': supplier}
                    ctx = orchestrator.resume_workflow(ctx, user_input)
                    st.session_state.workflow_context = ctx

                # ✅ MD MADDE 3: Navigate based on workflow status
                if ctx.workflow_status == WorkflowStatus.REQUIRES_APPROVAL:
                    st.session_state.page = 'approval'
                elif ctx.workflow_status == WorkflowStatus.SUCCESS:
                    st.session_state.page = 'order'
                elif ctx.workflow_status == WorkflowStatus.FAILED:
                    st.error("❌ Workflow failed")
                    st.session_state.page = 'inbox'

                st.rerun()

            st.divider()


# =========================
# PAGE: APPROVAL
# =========================
def page_approval():
    """MD madde 3 & 4: Approval flow - orchestrator.resume_workflow() ile manager onayı"""
    st.title("📧 Email Agent - Approval Request")

    # ✅ MD MADDE 4: UI Data Binding - context'ten veri al
    ctx = get_context()

    if not ctx or not ctx.approval_email:
        st.error("No approval data found.")
        if st.button("← Back"):
            st.session_state.page = 'inbox'
            st.rerun()
        return

    approval = ctx.approval_email

    if st.button("← Back"):
        st.session_state.page = 'compliance'
        st.rerun()

    st.divider()
    st.markdown("### 📨 Approval Email Preview")
    st.markdown("#### ✏️ Edit Email Content")

    manager_email = st.text_input(
        "To:",
        value=approval.get('manager_email', 'manager@greypine.com'),
        key="edit_manager_email"
    )

    subject = st.text_input(
        "Subject:",
        value=approval.get('subject', 'Approval Required'),
        key="edit_subject"
    )

    body = st.text_area(
        "Email Body:",
        value=approval.get('body', 'Email body'),
        height=200,
        key="edit_body"
    )

    if st.button("💾 Save Changes"):
        # ✅ MD MADDE 4: Context'i güncelle
        ctx.approval_email = {
            'manager_email': manager_email,
            'subject': subject,
            'body': body
        }
        st.session_state.workflow_context = ctx
        st.success("✅ Email updated!")
        time.sleep(1)
        st.rerun()

    st.divider()
    st.markdown(
        "**Would you like to proceed with approval request from the requester's manager?**")

    col1, col2 = st.columns(2)

    if col1.button("✅ Yes, Send Approval", type="primary") and not st.session_state.approval_sent:
        ctx.approval_email = {
            'manager_email': manager_email,
            'subject': subject,
            'body': body
        }
        st.session_state.workflow_context = ctx
        st.session_state.approval_sent = True
        st.rerun()

    if col2.button("❌ No, Cancel"):
        st.session_state.approval_sent = False
        st.session_state.page = 'inbox'
        st.rerun()

    if st.session_state.approval_sent:
        st.success("📤 Approval request sent successfully!")

        # Reminder scheduling
        st.divider()
        st.markdown("### ⏰ Schedule Email Reminder")
        st.info("To expedite the approval process, schedule automatic reminder emails.")

        reminder_interval = st.selectbox(
            "Select reminder interval:",
            options=[5, 30, 60, 120, 1440],
            format_func=lambda x: f"{x} minutes" if x < 60 else f"{x//60} hour(s)" if x < 1440 else "1 day",
            index=2,
            key="reminder_interval_select"
        )

        if st.button("📅 Schedule Email Reminder", key="schedule_reminder_btn"):
            reminder = schedule_reminder(
                manager_email, subject, reminder_interval)
            st.session_state.scheduled_reminders.append(reminder)
            add_history(
                "⏰ Reminder Scheduled",
                f"To: {manager_email} at {reminder['scheduled_time']} ({reminder['interval']})",
                "success"
            )
            st.success(
                f"✅ Reminder scheduled for {reminder['scheduled_time']}")

        st.divider()

        # ✅ MD MADDE 3: Manager approval - orchestrator.resume_workflow() ile
        st.markdown("### 🎭 Simulate Manager Response")
        st.caption("In production, this waits for actual manager response.")

        col_approve, col_reject = st.columns(2)

        if col_approve.button("✅ Manager Approves", type="primary", key="manager_approve"):
            orchestrator = st.session_state.orchestrator

            with st.spinner("🤖 Orchestrator: Completing workflow..."):
                # ✅ MD MADDE 3: Resume workflow with manager approval
                user_input = {'manager_approved': True}
                ctx = orchestrator.resume_workflow(ctx, user_input)
                st.session_state.workflow_context = ctx

            add_history("✅ Manager Approval",
                        "Request approved by manager", "success")
            st.session_state.approval_sent = False
            time.sleep(1)
            st.session_state.page = 'order'
            st.rerun()

        if col_reject.button("❌ Manager Rejects", type="secondary", key="manager_reject"):
            add_history("❌ Manager Approval",
                        "Request rejected by manager", "error")
            st.session_state.approval_sent = False
            time.sleep(1)
            st.session_state.page = 'inbox'
            st.rerun()


# =========================
# PAGE: ORDER
# =========================
def page_order():
    """MD madde 4: Order sayfası - tüm veriler context'ten"""
    st.title("🎉 Order Placed Successfully!")

    # ✅ MD MADDE 4: UI Data Binding - tüm veriler context'ten gelir
    ctx = get_context()

    if not ctx:
        st.error("No workflow context found.")
        return

    request = ctx.purchase_request
    supplier = ctx.selected_supplier
    order = ctx.order_result

    total = supplier.price_per_unit * request.quantity

    st.balloons()
    st.divider()

    # ✅ MD MADDE 5: Orchestrator Monitoring - Execution summary
    st.markdown("### 🤖 Workflow Execution Summary")
    summary = st.session_state.orchestrator.get_execution_summary(ctx)

    col1, col2, col3 = st.columns(3)
    col1.metric("Agents Executed", summary['total_agents_executed'])
    col2.metric("Total Time", summary['total_execution_time'])
    col3.metric("Status", "✅ SUCCESS")

    with st.expander("📋 Execution Log"):
        for log in ctx.execution_log:
            st.text(
                f"🕐 {log['timestamp']} | {log['agent']:20s} | {log['status']}")

    st.divider()

    st.markdown("### 📦 Order Summary")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**Item:** {request.item}")
        st.markdown(f"**Quantity:** {request.quantity}")
        st.markdown(f"**Supplier:** {supplier.name}")

    with col2:
        st.markdown(f"**Unit Price:** {supplier.price_per_unit} TL")
        st.markdown(f"**Total Cost:** {total} TL")
        st.markdown(f"**Status:** ✅ ORDER_PLACED")

    st.divider()

    if st.button("🔙 Return to Inbox", type="primary"):
        # Reset workflow context
        st.session_state.workflow_context = None
        st.session_state.approval_sent = False
        st.session_state.page = 'inbox'
        st.rerun()


# =========================
# PAGE: HISTORY
# =========================
def page_history():
    st.title("📜 Process History & Timeline")

    if st.button("← Back"):
        st.session_state.page = 'inbox'
        st.rerun()

    st.divider()

    # Scheduled reminders
    reminders = st.session_state.get('scheduled_reminders', [])
    if reminders:
        st.markdown("### ⏰ Scheduled Reminders")
        for reminder in reminders:
            with st.container():
                col1, col2, col3 = st.columns([2, 2, 3])
                col1.markdown(f"📧 **{reminder['to']}**")
                col2.markdown(f"🕐 {reminder['scheduled_time']}")
                col3.markdown(f"📝 {reminder['subject'][:40]}...")
                st.caption(
                    f"Interval: {reminder['interval']} | Status: ⏳ {reminder['status']}")
                st.divider()

    history = st.session_state.history

    if not history:
        st.info("🔍 No actions recorded yet.")
        return

    st.markdown(f"### 📊 Total Actions: {len(history)}")
    st.divider()

    for event in reversed(history):
        if event['status'] == 'success':
            emoji = "✅"
        elif event['status'] == 'warning':
            emoji = "⚠️"
        elif event['status'] == 'error':
            emoji = "❌"
        else:
            emoji = "🔵"

        with st.container():
            col1, col2, col3 = st.columns([1, 3, 6])
            col1.markdown(f"**{event['timestamp']}**")
            col2.markdown(f"{emoji} **{event['action']}**")
            col3.markdown(f"_{event['details']}_")
            st.divider()

    if st.button("🗑️ Clear History", type="secondary"):
        st.session_state.history = []
        st.success("History cleared!")
        time.sleep(1)
        st.rerun()


# =========================
# MAIN ROUTER
# =========================
def main():
    # Session state initialization
    init_session_state()

    # ✅ MD MADDE 5: Sidebar - Orchestrator Monitoring
    with st.sidebar:
        st.markdown("### 🤖 Procurement Assistant")
        st.markdown("Powered by IBM watsonx Orchestrate")
        st.divider()

        if st.button("📜 View History", use_container_width=True):
            st.session_state.page = 'history'
            st.rerun()

        st.divider()

        steps = {
            'inbox': '1️⃣ Email Inbox',
            'detail': '2️⃣ Email Detail',
            'sourcing': '3️⃣ Supplier Selection',
            'compliance': '4️⃣ Compliance Check',
            'approval': '5️⃣ Approval Flow',
            'order': '6️⃣ Order Confirmation',
            'history': '📜 Process History'
        }

        current_step = steps.get(st.session_state.page, 'Unknown')
        st.info(f"**Current Step:**\n{current_step}")

        # Metrics
        history_count = len(st.session_state.get('history', []))
        reminder_count = len(st.session_state.get('scheduled_reminders', []))
        col1, col2 = st.columns(2)
        if history_count > 0:
            col1.metric("Actions", history_count)
        if reminder_count > 0:
            col2.metric("⏰ Reminders", reminder_count)

        # ✅ MD MADDE 5: Orchestrator Monitoring UI
        ctx = st.session_state.get('workflow_context')
        if ctx and ORCHESTRATOR_AVAILABLE:
            st.divider()
            st.markdown("### 🤖 Orchestrator Status")

            status_map = {
                WorkflowStatus.PENDING: ("⏸️", "Awaiting supplier"),
                WorkflowStatus.IN_PROGRESS: ("▶️", "Running"),
                WorkflowStatus.SUCCESS: ("✅", "Completed"),
                WorkflowStatus.FAILED: ("❌", "Failed"),
                WorkflowStatus.REQUIRES_APPROVAL: ("⚠️", "Needs approval"),
            }
            emoji, label = status_map.get(
                ctx.workflow_status, ("❓", "Unknown"))

            st.markdown(f"**Status:** {emoji} {label}")

            if ctx.current_step:
                st.markdown(f"**Last Agent:** `{ctx.current_step}`")

            agents_run = len(ctx.execution_log)
            if agents_run > 0:
                st.metric("Agents Executed", agents_run)

            # Execution log in expander
            if ctx.execution_log:
                with st.expander("📋 Execution Log"):
                    for log in ctx.execution_log:
                        st.text(
                            f"{log['timestamp']} {log['agent']}: {log['status']}")

    # Page routing
    page = st.session_state.page

    if page == 'inbox':
        page_inbox()
    elif page == 'detail':
        page_detail()
    elif page == 'sourcing':
        page_sourcing()
    elif page == 'approval':
        page_approval()
    elif page == 'order':
        page_order()
    elif page == 'history':
        page_history()


if __name__ == "__main__":
    main()
