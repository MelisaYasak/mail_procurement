# orchestrator.py
# IBM watsonx Orchestrate-style Orchestrator

from dataclasses import dataclass
from typing import Dict, Any, List, Callable
from enum import Enum
import time
from datetime import datetime


class WorkflowStatus(Enum):
    """Workflow execution statuses"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    REQUIRES_APPROVAL = "requires_approval"


class AgentStatus(Enum):
    """Individual agent execution statuses"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentResult:
    """Result from an agent execution"""
    agent_name: str
    status: AgentStatus
    data: Any
    error: str = None
    execution_time: float = 0.0


@dataclass
class WorkflowContext:
    """Shared context passed between agents"""
    email_id: int
    email_data: Dict[str, Any]
    purchase_request: Any = None
    suppliers: List[Any] = None
    selected_supplier: Any = None
    compliance_result: tuple = None
    approval_email: Dict[str, Any] = None
    order_result: Dict[str, Any] = None

    # Metadata
    workflow_status: WorkflowStatus = WorkflowStatus.PENDING
    current_step: str = None
    execution_log: List[Dict] = None

    def __post_init__(self):
        if self.execution_log is None:
            self.execution_log = []


class ProcurementOrchestrator:
    """
    IBM watsonx Orchestrate-inspired orchestrator
    Coordinates multiple agents in a procurement workflow
    """

    def __init__(self):
        # Register agents
        self.agents: Dict[str, Callable] = {}

        # Workflow definition
        self.workflow_steps = [
            "email_agent",
            "supplier_agent",
            "compliance_agent",
            "approval_agent",  # Conditional
            "order_agent"
        ]

        # Execution history
        self.execution_history: List[WorkflowContext] = []

    def register_agent(self, name: str, agent_func: Callable):
        """Register an agent with the orchestrator"""
        self.agents[name] = agent_func
        self._log(f"Agent registered: {name}")

    def _log(self, message: str, level: str = "INFO"):
        """Internal logging"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] Orchestrator: {message}")

    def _execute_agent(
        self,
        agent_name: str,
        context: WorkflowContext,
        **kwargs
    ) -> AgentResult:
        """Execute a single agent with error handling"""

        if agent_name not in self.agents:
            return AgentResult(
                agent_name=agent_name,
                status=AgentStatus.FAILED,
                data=None,
                error=f"Agent '{agent_name}' not registered"
            )

        self._log(f"Executing agent: {agent_name}")
        context.current_step = agent_name

        start_time = time.time()

        try:
            agent_func = self.agents[agent_name]
            result_data = agent_func(context, **kwargs)

            execution_time = time.time() - start_time

            # Log execution
            context.execution_log.append({
                'timestamp': datetime.now().strftime("%H:%M:%S"),
                'agent': agent_name,
                'status': 'success',
                'execution_time': f"{execution_time:.2f}s"
            })

            self._log(
                f"Agent '{agent_name}' completed in {execution_time:.2f}s")

            return AgentResult(
                agent_name=agent_name,
                status=AgentStatus.COMPLETED,
                data=result_data,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - start_time

            error_msg = f"Agent '{agent_name}' failed: {str(e)}"
            self._log(error_msg, level="ERROR")

            context.execution_log.append({
                'timestamp': datetime.now().strftime("%H:%M:%S"),
                'agent': agent_name,
                'status': 'failed',
                'error': str(e),
                'execution_time': f"{execution_time:.2f}s"
            })

            return AgentResult(
                agent_name=agent_name,
                status=AgentStatus.FAILED,
                data=None,
                error=str(e),
                execution_time=execution_time
            )

    def execute_workflow(
        self,
        email_data: Dict[str, Any],
        user_selections: Dict[str, Any] = None
    ) -> WorkflowContext:
        """
        Execute the complete procurement workflow

        Args:
            email_data: Email to process
            user_selections: Optional user inputs (supplier selection, etc.)

        Returns:
            WorkflowContext with results
        """

        self._log("=" * 60)
        self._log("Starting procurement workflow")
        self._log("=" * 60)

        # Initialize context
        context = WorkflowContext(
            email_id=email_data.get('id'),
            email_data=email_data
        )

        context.workflow_status = WorkflowStatus.IN_PROGRESS

        # Step 1: Email Agent - Extract purchase request
        result = self._execute_agent('email_agent', context)

        if result.status == AgentStatus.FAILED:
            context.workflow_status = WorkflowStatus.FAILED
            return context

        context.purchase_request = result.data

        # Step 2: Supplier Agent - Find suppliers
        result = self._execute_agent('supplier_agent', context)

        if result.status == AgentStatus.FAILED:
            context.workflow_status = WorkflowStatus.FAILED
            return context

        context.suppliers = result.data

        # Step 2.5: Wait for user to select supplier (if not provided)
        if user_selections and 'selected_supplier' in user_selections:
            context.selected_supplier = user_selections['selected_supplier']
        else:
            # In interactive mode, workflow pauses here
            context.workflow_status = WorkflowStatus.PENDING
            self._log("Workflow paused: Awaiting supplier selection")
            return context

        # Step 3: Compliance Agent - Check compliance
        result = self._execute_agent('compliance_agent', context)

        if result.status == AgentStatus.FAILED:
            context.workflow_status = WorkflowStatus.FAILED
            return context

        context.compliance_result = result.data
        is_compliant, reason = result.data

        # Step 4: Conditional - Approval if non-compliant
        if not is_compliant:
            context.workflow_status = WorkflowStatus.REQUIRES_APPROVAL

            result = self._execute_agent(
                'approval_agent', context, reason=reason)

            if result.status == AgentStatus.FAILED:
                context.workflow_status = WorkflowStatus.FAILED
                return context

            context.approval_email = result.data

            # Wait for manager approval (would be async in production)
            self._log("Workflow paused: Awaiting manager approval")

            if user_selections and user_selections.get('manager_approved') == False:
                context.workflow_status = WorkflowStatus.FAILED
                self._log("Workflow terminated: Manager rejected")
                return context

        # Step 5: Order Agent - Place order
        result = self._execute_agent('order_agent', context)

        if result.status == AgentStatus.FAILED:
            context.workflow_status = WorkflowStatus.FAILED
            return context

        context.order_result = result.data
        context.workflow_status = WorkflowStatus.SUCCESS

        self._log("=" * 60)
        self._log("Workflow completed successfully!")
        self._log("=" * 60)

        # Store in history
        self.execution_history.append(context)

        return context

    def get_workflow_status(self, email_id: int) -> WorkflowContext:
        """Get current workflow status for an email"""
        for workflow in self.execution_history:
            if workflow.email_id == email_id:
                return workflow
        return None

    def resume_workflow(
        self,
        context: WorkflowContext,
        user_input: Dict[str, Any]
    ) -> WorkflowContext:
        """
        Resume a paused workflow with user input

        Used when workflow needs user decisions (supplier selection, approval)
        """

        self._log(f"Resuming workflow for email #{context.email_id}")

        # Update context with user input
        if 'selected_supplier' in user_input:
            context.selected_supplier = user_input['selected_supplier']

        if 'manager_approved' in user_input:
            # Continue from approval step
            pass

        # Re-execute workflow from current step
        return self.execute_workflow(
            context.email_data,
            user_selections=user_input
        )

    def get_execution_summary(self, context: WorkflowContext) -> Dict[str, Any]:
        """Generate execution summary"""

        total_time = sum(
            float(log['execution_time'].rstrip('s'))
            for log in context.execution_log
            if 'execution_time' in log
        )

        return {
            'email_id': context.email_id,
            'status': context.workflow_status.value,
            'total_agents_executed': len(context.execution_log),
            'total_execution_time': f"{total_time:.2f}s",
            'current_step': context.current_step,
            'requires_approval': context.workflow_status == WorkflowStatus.REQUIRES_APPROVAL,
            'execution_log': context.execution_log
        }


# =========================
# EXAMPLE USAGE
# =========================

if __name__ == "__main__":

    # Initialize orchestrator
    orchestrator = ProcurementOrchestrator()

    # Mock agents (in real system, these would be your actual agents)
    def mock_email_agent(context, **kwargs):
        print(f"  📨 Email Agent processing: {context.email_data['subject']}")
        time.sleep(0.5)
        return {'item': 'laptops', 'quantity': 10, 'budget': 80000}

    def mock_supplier_agent(context, **kwargs):
        print(
            f"  🏭 Supplier Agent finding suppliers for: {context.purchase_request['item']}")
        time.sleep(0.5)
        return [
            {'name': 'Supplier_A', 'price': 7500},
            {'name': 'Supplier_B', 'price': 8200}
        ]

    def mock_compliance_agent(context, **kwargs):
        print(
            f"  📋 Compliance Agent checking supplier: {context.selected_supplier['name']}")
        time.sleep(0.3)
        total = context.selected_supplier['price'] * \
            context.purchase_request['quantity']
        is_compliant = total <= context.purchase_request['budget']
        reason = "" if is_compliant else f"Budget exceeded: {total} > {context.purchase_request['budget']}"
        return (is_compliant, reason)

    def mock_approval_agent(context, **kwargs):
        print(f"  📧 Approval Agent creating email for: {kwargs.get('reason')}")
        time.sleep(0.3)
        return {'subject': 'Approval Required', 'body': 'Please approve...'}

    def mock_order_agent(context, **kwargs):
        print(
            f"  🧾 Order Agent placing order with: {context.selected_supplier['name']}")
        time.sleep(0.3)
        return {'order_id': 'ORD-12345', 'status': 'PLACED'}

    # Register agents
    orchestrator.register_agent('email_agent', mock_email_agent)
    orchestrator.register_agent('supplier_agent', mock_supplier_agent)
    orchestrator.register_agent('compliance_agent', mock_compliance_agent)
    orchestrator.register_agent('approval_agent', mock_approval_agent)
    orchestrator.register_agent('order_agent', mock_order_agent)

    # Execute workflow
    email = {
        'id': 1,
        'subject': 'Laptop Purchase Request',
        'body': 'Need 10 laptops, budget 80000 TL'
    }

    # First execution - will pause for supplier selection
    context = orchestrator.execute_workflow(email)
    print(f"\n📊 Status: {context.workflow_status.value}")

    # User selects supplier
    context = orchestrator.resume_workflow(context, {
        'selected_supplier': {'name': 'Supplier_A', 'price': 7500}
    })

    # Print summary
    summary = orchestrator.get_execution_summary(context)
    print(f"\n{'='*60}")
    print("EXECUTION SUMMARY")
    print(f"{'='*60}")
    for key, value in summary.items():
        if key != 'execution_log':
            print(f"{key}: {value}")
