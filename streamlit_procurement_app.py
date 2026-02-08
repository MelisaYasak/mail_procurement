import streamlit as st
from dataclasses import dataclass
from typing import List, Dict, Any
import time

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import JsonOutputParser

# 🆕 Import orchestrator
try:
    from orchestrator import (
        ProcurementOrchestrator,
        WorkflowContext,
        WorkflowStatus,
        AgentResult,
        AgentStatus
    )
    ORCHESTRATOR_AVAILABLE = True
except ImportError:
    ORCHESTRATOR_AVAILABLE = False
    print("⚠️ Orchestrator module not found - running in legacy mode")


# =========================
# SESSION STATE INIT
# =========================
if 'page' not in st.session_state:
    st.session_state.page = 'inbox'
if 'selected_email' not in st.session_state:
    st.session_state.selected_email = None
if 'purchase_request' not in st.session_state:
    st.session_state.purchase_request = None
if 'suppliers' not in st.session_state:
    st.session_state.suppliers = None
if 'selected_supplier' not in st.session_state:
    st.session_state.selected_supplier = None
if 'approval_email' not in st.session_state:
    st.session_state.approval_email = None
if 'history' not in st.session_state:
    st.session_state.history = []
if 'scheduled_reminders' not in st.session_state:
    st.session_state.scheduled_reminders = []
if 'workflow_context' not in st.session_state:
    st.session_state.workflow_context = None
if 'orchestrator' not in st.session_state:
    st.session_state.orchestrator = initialize_orchestrator(
    ) if ORCHESTRATOR_AVAILABLE else None
    if st.session_state.orchestrator:
        add_history(
            "System", "Orchestrator initialized with 5 agents", "success")


# =========================
# HISTORY HELPER
# =========================
def add_history(action: str, details: str, status: str = "success"):
    """Add event to history with timestamp"""
    from datetime import datetime

    st.session_state.history.append({
        'timestamp': datetime.now().strftime("%H:%M:%S"),
        'action': action,
        'details': details,
        'status': status
    })


# =========================
# REMINDER SCHEDULING
# =========================
def schedule_reminder(manager_email: str, subject: str, interval_minutes: int):
    """
    Schedule an email reminder
    In production: would integrate with email service (SendGrid, etc.)
    Here: simulated
    """
    from datetime import datetime, timedelta

    reminder_time = datetime.now() + timedelta(minutes=interval_minutes)

    return {
        'to': manager_email,
        'subject': f"REMINDER: {subject}",
        'scheduled_time': reminder_time.strftime("%H:%M:%S"),
        'interval': f"{interval_minutes} minutes",
        'status': 'scheduled'
    }


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
# MOCK DATA - EMAILS
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
# AGENTS
# =========================

# Email Agent
email_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Extract purchase request from email. Return JSON with: item, quantity, budget.\n"
     "Example: {{\"item\": \"laptop\", \"quantity\": 5, \"budget\": 50000.0}}"),
    ("human", "{email}")
])


def email_agent(email_text: str) -> PurchaseRequest:
    """Legacy email agent - for backward compatibility"""
    chain = email_prompt | llm | JsonOutputParser()
    data = chain.invoke({"email": email_text})
    return PurchaseRequest(
        item=data["item"],
        quantity=int(data["quantity"]),
        budget=float(data["budget"])
    )


def email_agent_wrapper(context, **kwargs):
    """Orchestrator-compatible email agent"""
    email_text = context.email_data.get('body', '')
    result = email_agent(email_text)
    add_history(
        "Email Agent", f"Extracted: {result.item} (qty: {result.quantity})", "success")
    return result


# Supplier Agent
supplier_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Return JSON with supplier info: name, price_per_unit, compliant.\n"
     "Generate 3 realistic suppliers with different prices."),
    ("human", "Item: {item}\nQuantity: {quantity}\nBudget: {budget}")
])


def supplier_agent(request: PurchaseRequest) -> List[Supplier]:
    """Returns multiple supplier options"""
    # Simulated - gerçekte database'den gelir
    import random
    base_price = request.budget / request.quantity

    suppliers = []
    for i in range(3):
        price_variation = random.uniform(0.8, 1.3)
        suppliers.append(Supplier(
            name=f"Supplier_{chr(65+i)}",  # A, B, C
            price_per_unit=round(base_price * price_variation, 2),
            compliant=random.choice([True, True, True, False])  # 75% compliant
        ))

    return suppliers


def supplier_agent_wrapper(context, **kwargs):
    """Orchestrator-compatible supplier agent"""
    request = context.purchase_request
    result = supplier_agent(request)
    add_history("Supplier Agent", f"Found {len(result)} suppliers", "success")
    return result


# Compliance Agent
def compliance_agent(supplier: Supplier, request: PurchaseRequest) -> tuple[bool, str]:
    total_cost = supplier.price_per_unit * request.quantity

    if not supplier.compliant:
        return False, "Supplier is not compliant with company policies"

    if total_cost > request.budget:
        return False, f"Budget exceeded: {total_cost} TL > {request.budget} TL"

    return True, ""


def compliance_agent_wrapper(context, **kwargs):
    """Orchestrator-compatible compliance agent"""
    supplier = context.selected_supplier
    request = context.purchase_request
    result = compliance_agent(supplier, request)
    is_compliant, reason = result
    status = "success" if is_compliant else "warning"
    add_history("Compliance Agent", reason if reason else "Passed", status)
    return result


# Approval Agent
approval_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Create approval email. Return JSON: subject, body, manager_email."),
    ("human",
     "Item: {item}\nQuantity: {quantity}\nSupplier: {supplier}\n"
     "Total: {total} TL\nBudget: {budget} TL\nReason: {reason}")
])


def approval_agent(request: PurchaseRequest, supplier: Supplier, reason: str) -> Dict[str, Any]:
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


def approval_agent_wrapper(context, **kwargs):
    """Orchestrator-compatible approval agent"""
    request = context.purchase_request
    supplier = context.selected_supplier
    reason = kwargs.get('reason', 'Approval required')
    result = approval_agent(request, supplier, reason)
    add_history("Approval Agent",
                f"Email created: {result.get('subject', 'N/A')}", "success")
    return result


# Order Agent
def order_agent_wrapper(context, **kwargs):
    """Orchestrator-compatible order agent"""
    supplier = context.selected_supplier
    request = context.purchase_request

    result = {
        "supplier": supplier.name,
        "item": request.item,
        "quantity": request.quantity,
        "total_price": supplier.price_per_unit * request.quantity,
        "status": "ORDER_PLACED"
    }

    add_history("Order Agent",
                f"Order placed: {result['total_price']} TL", "success")
    return result


# =========================
# ORCHESTRATOR INITIALIZATION
# =========================

def initialize_orchestrator():
    """Initialize and register all agents with orchestrator"""
    if ORCHESTRATOR_AVAILABLE:
        orchestrator = ProcurementOrchestrator()

        # Register all agents
        orchestrator.register_agent('email_agent', email_agent_wrapper)
        orchestrator.register_agent('supplier_agent', supplier_agent_wrapper)
        orchestrator.register_agent(
            'compliance_agent', compliance_agent_wrapper)
        orchestrator.register_agent('approval_agent', approval_agent_wrapper)
        orchestrator.register_agent('order_agent', order_agent_wrapper)

        return orchestrator
    return None


def approval_agent(request: PurchaseRequest, supplier: Supplier, reason: str) -> Dict[str, Any]:
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


# =========================
# UI PAGES
# =========================

def page_inbox():
    """IBM Step 1-2: Email Inbox & Classification"""
    st.title("🏢 Greypine Procurement Assistant")
    st.markdown("**AI-enabled Supplier Engagement Portal**")

    st.divider()

    # Step 1: Read emails button
    st.subheader("📨 Email Management")

    if st.button("📧 Read and classify unread emails in Outlook", type="primary"):
        with st.spinner("Connecting to Outlook and classifying emails..."):
            time.sleep(1)  # Simulate loading
            st.session_state.emails_loaded = True

    # Step 2: Show email list if loaded
    if st.session_state.get('emails_loaded'):
        st.success("✅ Emails classified successfully!")

        # Filter by category
        st.markdown("### 📋 Category: Procurement Requests")

        procurement_emails = [
            e for e in MOCK_EMAILS if e.category == "Procurement Request"]

        # Display emails as cards
        for email in procurement_emails:
            with st.container():
                col1, col2 = st.columns([4, 1])

                with col1:
                    priority_emoji = "🔴" if email.priority == "High" else "🟡" if email.priority == "Medium" else "🟢"
                    st.markdown(f"**{priority_emoji} From:** {email.sender}")
                    st.markdown(f"**Subject:** {email.subject}")

                with col2:
                    if st.button(f"Select", key=f"select_{email.id}"):
                        # 🆕 ORCHESTRATOR MODE
                        if ORCHESTRATOR_AVAILABLE and st.session_state.orchestrator:
                            orchestrator = st.session_state.orchestrator

                            # Start workflow
                            email_data = {
                                'id': email.id,
                                'sender': email.sender,
                                'subject': email.subject,
                                'body': email.body
                            }

                            with st.spinner("🤖 Orchestrator processing workflow..."):
                                # Execute workflow (will pause at supplier selection)
                                context = orchestrator.execute_workflow(
                                    email_data)
                                st.session_state.workflow_context = context
                                st.session_state.selected_email = email

                            # Navigate based on workflow status
                            if context.workflow_status == WorkflowStatus.PENDING:
                                # Waiting for supplier selection
                                st.session_state.page = 'sourcing'
                            else:
                                st.session_state.page = 'detail'

                            st.rerun()
                        else:
                            # Legacy mode
                            st.session_state.selected_email = email
                            add_history(
                                "Email Selected", f"From: {email.sender} - {email.subject}")
                            st.session_state.page = 'detail'
                            st.rerun()

                st.divider()


def page_detail():
    """IBM Step 3: Email Detail & Purchase Request Initiation"""
    st.title("📧 Email Details")

    email = st.session_state.selected_email

    if st.button("← Back to Inbox"):
        st.session_state.page = 'inbox'
        st.rerun()

    st.divider()

    # Email summary
    st.markdown(f"### From: {email.sender}")
    st.markdown(f"**Subject:** {email.subject}")
    st.markdown(f"**Priority:** {email.priority}")

    st.info(f"📄 **Email Content:**\n\n{email.body}")

    st.divider()

    # IBM: User types "Can you initiate a purchase request for this item?"
    st.markdown("### 💬 Your Response")

    user_input = st.text_input(
        "Type your request:",
        placeholder="Can you initiate a purchase request for this item?"
    )

    if st.button("Send", type="primary") or user_input:
        if "purchase" in user_input.lower() or "initiate" in user_input.lower():
            with st.spinner("🔄 Extracting purchase request and contacting Sourcing Agent..."):
                # Email Agent extracts request
                st.session_state.purchase_request = email_agent(email.body)
                add_history(
                    "Purchase Request Created",
                    f"Item: {st.session_state.purchase_request.item}, Qty: {st.session_state.purchase_request.quantity}"
                )
                time.sleep(1)

            st.success("✅ Purchase request created!")
            st.session_state.page = 'sourcing'
            st.rerun()
        else:
            st.warning("Please request to initiate a purchase request.")


def page_sourcing():
    """IBM Step 4: Supplier Selection"""
    st.title("🏭 Sourcing Agent - Supplier Selection")

    # 🆕 Get data from orchestrator context if available
    if st.session_state.workflow_context:
        context = st.session_state.workflow_context
        request = context.purchase_request
        suppliers = context.suppliers
    else:
        # Legacy mode
        request = st.session_state.purchase_request
        suppliers = st.session_state.suppliers

    if st.button("← Back"):
        st.session_state.page = 'detail'
        st.rerun()

    st.divider()

    # Show procurement details
    st.markdown("### 📦 Procurement Details")
    col1, col2, col3 = st.columns(3)
    col1.metric("Item", request.item)
    col2.metric("Quantity", request.quantity)
    col3.metric("Budget", f"{request.budget} TL")

    st.divider()

    # 🆕 Suppliers already loaded by orchestrator
    st.markdown("### 🏢 Available Suppliers")
    st.info("✨ Suppliers found by Orchestrator's Sourcing Agent")

    # Display as table
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
                # 🆕 ORCHESTRATOR MODE
                if ORCHESTRATOR_AVAILABLE and st.session_state.orchestrator and st.session_state.workflow_context:
                    orchestrator = st.session_state.orchestrator
                    context = st.session_state.workflow_context

                    with st.spinner("🤖 Orchestrator resuming workflow..."):
                        # Resume workflow with supplier selection
                        user_input = {'selected_supplier': supplier}
                        context = orchestrator.resume_workflow(
                            context, user_input)
                        st.session_state.workflow_context = context

                    # Navigate based on workflow status
                    if context.workflow_status == WorkflowStatus.REQUIRES_APPROVAL:
                        st.session_state.page = 'approval'
                    elif context.workflow_status == WorkflowStatus.SUCCESS:
                        st.session_state.page = 'order'
                    elif context.workflow_status == WorkflowStatus.FAILED:
                        st.error("❌ Workflow failed")
                        st.session_state.page = 'inbox'

                    st.rerun()
                else:
                    # Legacy mode
                    st.session_state.selected_supplier = supplier
                    add_history(
                        "Supplier Selected", f"{supplier.name} - {supplier.price_per_unit} TL/unit")
                    st.session_state.page = 'compliance'
                    st.rerun()

            st.divider()


def page_compliance():
    """IBM Step 5: Compliance Check"""
    st.title("📋 Compliance Agent - Validation")

    supplier = st.session_state.selected_supplier
    request = st.session_state.purchase_request

    if st.button("← Back to Supplier Selection"):
        st.session_state.page = 'sourcing'
        st.rerun()

    st.divider()

    st.markdown("### 🔍 Running Compliance Check...")

    progress_bar = st.progress(0)
    for i in range(100):
        time.sleep(0.01)
        progress_bar.progress(i + 1)

    # Run compliance
    is_compliant, reason = compliance_agent(supplier, request)

    st.divider()

    if is_compliant:
        st.success("✅ Compliance check passed!")
        add_history("Compliance Check",
                    "Passed - All requirements met", "success")
        st.session_state.page = 'order'
        time.sleep(1)
        st.rerun()
    else:
        st.error(f"❌ Compliance Issue: {reason}")
        st.warning("🔔 Approval required from manager")
        add_history("Compliance Check", f"Failed - {reason}", "warning")

        if st.button("📧 Send Approval Request", type="primary"):
            with st.spinner("Generating approval email..."):
                st.session_state.approval_email = approval_agent(
                    request, supplier, reason)
                add_history(
                    "Approval Request", f"Email sent to {st.session_state.approval_email.get('manager_email', 'manager')}")
                time.sleep(1)
            st.session_state.page = 'approval'
            st.rerun()


def page_approval():
    """IBM Step 6: Approval Flow"""
    st.title("📧 Email Agent - Approval Request")

    # 🆕 Get approval data from orchestrator context if available
    if st.session_state.workflow_context:
        context = st.session_state.workflow_context
        approval = context.approval_email
    else:
        approval = st.session_state.approval_email

    if st.button("← Back"):
        st.session_state.page = 'compliance'
        st.rerun()

    st.divider()

    st.markdown("### 📨 Approval Email Preview")

    # Editable fields
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

    # Save changes button
    if st.button("💾 Save Changes"):
        updated_email = {
            'manager_email': manager_email,
            'subject': subject,
            'body': body
        }

        if st.session_state.workflow_context:
            st.session_state.workflow_context.approval_email = updated_email
        else:
            st.session_state.approval_email = updated_email

        st.success("✅ Email updated!")
        time.sleep(1)
        st.rerun()

    st.divider()

    st.markdown(
        "**Would you like to proceed with approval request from the requester's manager?**")

    col1, col2 = st.columns(2)

    # State to track if approval was sent
    if 'approval_sent' not in st.session_state:
        st.session_state.approval_sent = False

    if col1.button("✅ Yes, Send Approval", type="primary") and not st.session_state.approval_sent:
        # Update approval with edited content
        if st.session_state.workflow_context:
            st.session_state.workflow_context.approval_email = {
                'manager_email': manager_email,
                'subject': subject,
                'body': body
            }
        else:
            st.session_state.approval_email = {
                'manager_email': manager_email,
                'subject': subject,
                'body': body
            }

        st.session_state.approval_sent = True
        st.rerun()

    if col2.button("❌ No, Cancel"):
        st.session_state.approval_sent = False
        st.session_state.page = 'inbox'
        st.rerun()

    # Show reminder scheduling UI after approval is sent
    if st.session_state.approval_sent:
        st.success("📤 Approval request sent successfully!")

        # 🆕 REMINDER SCHEDULING
        st.divider()
        st.markdown("### ⏰ Schedule Email Reminder")
        st.info(
            "To expedite the approval process, you can schedule automatic reminder emails.")

        reminder_interval = st.selectbox(
            "Select reminder interval:",
            options=[5, 30, 60, 120, 1440],
            format_func=lambda x: f"{x} minutes" if x < 60 else f"{x//60} hour(s)" if x < 1440 else "1 day",
            index=2,  # Default: 1 hour
            key="reminder_interval_select"
        )

        if st.button("📅 Schedule Email Reminder", key="schedule_reminder_btn"):
            reminder = schedule_reminder(
                manager_email, subject, reminder_interval)
            st.session_state.scheduled_reminders.append(reminder)

            add_history(
                "Reminder Scheduled",
                f"Reminder to {manager_email} at {reminder['scheduled_time']} ({reminder['interval']})",
                "success"
            )

            st.success(
                f"✅ Reminder scheduled for {reminder['scheduled_time']} ({reminder['interval']} from now)")

        st.divider()

        # Manual manager approval simulation
        st.markdown("### 🎭 Simulate Manager Response")
        st.caption(
            "In production, this would wait for actual manager response. For demo purposes, simulate the response:")

        col_approve, col_reject = st.columns(2)

        if col_approve.button("✅ Manager Approves", type="primary", key="manager_approve"):
            # 🆕 ORCHESTRATOR MODE
            if ORCHESTRATOR_AVAILABLE and st.session_state.orchestrator and st.session_state.workflow_context:
                orchestrator = st.session_state.orchestrator
                context = st.session_state.workflow_context

                with st.spinner("🤖 Orchestrator completing workflow..."):
                    # Resume workflow with approval
                    user_input = {'manager_approved': True}
                    context = orchestrator.resume_workflow(context, user_input)
                    st.session_state.workflow_context = context

                st.success("✅ Manager approved the request!")
                add_history("Manager Approval", "Request approved", "success")
                st.session_state.approval_sent = False
                time.sleep(1)
                st.session_state.page = 'order'
                st.rerun()
            else:
                # Legacy mode
                st.success("✅ Manager approved the request!")
                add_history("Manager Approval", "Request approved", "success")
                st.session_state.approval_sent = False
                time.sleep(1)
                st.session_state.page = 'order'
                st.rerun()

        if col_reject.button("❌ Manager Rejects", type="secondary", key="manager_reject"):
            st.error("❌ Manager rejected the request")
            add_history("Manager Approval", "Request rejected", "error")
            st.session_state.approval_sent = False
            time.sleep(1)
            st.session_state.page = 'inbox'
            st.rerun()


def page_order():
    """IBM Step 7: Order Confirmation"""
    st.title("🎉 Order Placed Successfully!")

    # 🆕 Get data from orchestrator context if available
    if st.session_state.workflow_context:
        context = st.session_state.workflow_context
        request = context.purchase_request
        supplier = context.selected_supplier

        # Show orchestrator success info
        st.success("✨ Workflow completed by Orchestrator!")

        # Display execution summary
        with st.expander("📊 Workflow Execution Summary"):
            summary = st.session_state.orchestrator.get_execution_summary(
                context)
            col1, col2 = st.columns(2)
            col1.metric("Agents Executed", summary['total_agents_executed'])
            col2.metric("Total Time", summary['total_execution_time'])

            st.markdown("**Execution Log:**")
            for log in context.execution_log:
                st.text(
                    f"{log['timestamp']} - {log['agent']}: {log['status']}")
    else:
        # Legacy mode
        request = st.session_state.purchase_request
        supplier = st.session_state.selected_supplier

    total = supplier.price_per_unit * request.quantity

    # Add to history
    if not st.session_state.workflow_context:
        add_history(
            "Order Placed",
            f"{request.quantity}x {request.item} from {supplier.name} - Total: {total} TL",
            "success"
        )

    st.balloons()

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
        # Reset state
        st.session_state.selected_email = None
        st.session_state.purchase_request = None
        st.session_state.suppliers = None
        st.session_state.selected_supplier = None
        st.session_state.approval_email = None
        st.session_state.page = 'inbox'
        st.rerun()


def page_history():
    """History/Timeline Page - Shows all actions"""
    st.title("📜 Process History & Timeline")

    if st.button("← Back"):
        st.session_state.page = 'inbox'
        st.rerun()

    st.divider()

    # 🆕 SCHEDULED REMINDERS SECTION
    reminders = st.session_state.get('scheduled_reminders', [])
    if reminders:
        st.markdown("### ⏰ Scheduled Reminders")

        for reminder in reminders:
            with st.container():
                col1, col2, col3 = st.columns([2, 3, 3])

                with col1:
                    st.markdown(f"📧 **{reminder['to']}**")

                with col2:
                    st.markdown(f"🕐 {reminder['scheduled_time']}")

                with col3:
                    st.markdown(f"📝 {reminder['subject'][:40]}...")

                st.caption(
                    f"Interval: {reminder['interval']} | Status: ⏳ {reminder['status']}")
                st.divider()

        st.divider()

    history = st.session_state.history

    if not history:
        st.info(
            "🔍 No actions recorded yet. Start a procurement process to see the timeline.")
        return

    st.markdown(f"### 📊 Total Actions: {len(history)}")
    st.divider()

    # Display history in reverse (newest first)
    for idx, event in enumerate(reversed(history)):
        # Status emoji
        if event['status'] == 'success':
            status_emoji = "✅"
            status_color = "green"
        elif event['status'] == 'warning':
            status_emoji = "⚠️"
            status_color = "orange"
        elif event['status'] == 'error':
            status_emoji = "❌"
            status_color = "red"
        else:
            status_emoji = "🔵"
            status_color = "blue"

        with st.container():
            col1, col2, col3 = st.columns([1, 3, 6])

            with col1:
                st.markdown(f"**{event['timestamp']}**")

            with col2:
                st.markdown(f"{status_emoji} **{event['action']}**")

            with col3:
                st.markdown(f"_{event['details']}_")

            st.divider()

    # Clear history button
    if st.button("🗑️ Clear History", type="secondary"):
        st.session_state.history = []
        st.success("History cleared!")
        time.sleep(1)
        st.rerun()


# =========================
# MAIN ROUTER
# =========================

def main():
    # Sidebar navigation (optional)
    with st.sidebar:
        st.image("https://via.placeholder.com/150x50/2E86AB/FFFFFF?text=Greypine",
                 use_container_width=True)
        st.markdown("### 🤖 Procurement Assistant")
        st.markdown("Powered by IBM watsonx Orchestrate")
        st.divider()

        # History button
        if st.button("📜 View History", use_container_width=True):
            st.session_state.page = 'history'
            st.rerun()

        st.divider()

        # Show current step
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

        # Show history count
        history_count = len(st.session_state.get('history', []))
        reminder_count = len(st.session_state.get('scheduled_reminders', []))

        col1, col2 = st.columns(2)
        if history_count > 0:
            col1.metric("Actions", history_count)
        if reminder_count > 0:
            col2.metric("⏰ Reminders", reminder_count)

        # 🆕 Orchestrator Status
        if ORCHESTRATOR_AVAILABLE and st.session_state.workflow_context:
            st.divider()
            st.markdown("### 🤖 Orchestrator Status")

            ctx = st.session_state.workflow_context
            status_emoji = {
                WorkflowStatus.PENDING: "⏸️",
                WorkflowStatus.IN_PROGRESS: "▶️",
                WorkflowStatus.SUCCESS: "✅",
                WorkflowStatus.FAILED: "❌",
                WorkflowStatus.REQUIRES_APPROVAL: "⚠️"
            }.get(ctx.workflow_status, "❓")

            st.markdown(
                f"**Status:** {status_emoji} {ctx.workflow_status.value}")

            if ctx.current_step:
                st.markdown(f"**Current Agent:** {ctx.current_step}")

            agents_executed = len(ctx.execution_log)
            if agents_executed > 0:
                st.metric("Agents Executed", agents_executed)

    # Route to correct page
    page = st.session_state.page

    if page == 'inbox':
        page_inbox()
    elif page == 'detail':
        page_detail()
    elif page == 'sourcing':
        page_sourcing()
    elif page == 'compliance':
        page_compliance()
    elif page == 'approval':
        page_approval()
    elif page == 'order':
        page_order()
    elif page == 'history':
        page_history()


if __name__ == "__main__":
    main()
