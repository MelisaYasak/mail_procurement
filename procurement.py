# multiagent_procurement_langchain.py

from dataclasses import dataclass
from typing import List, Dict, Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import JsonOutputParser


# =========================
# LLM
# =========================

llm = ChatOllama(
    model="qwen2.5:3b",
    temperature=0
)


# =========================
# MODELLER
# =========================

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


@dataclass
class EvaluationResult:
    email_id: int
    status: str
    reason: str | None
    order: Dict[str, Any] | None


# =========================
# EMAIL AGENT (LLM)
# =========================

email_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You extract a structured purchase request from an email. "
     "Return ONLY valid JSON with keys: item, quantity, budget.\n"
     "quantity MUST be a single integer number.\n"
     "budget MUST be a single float number.\n"
     "Example: {{\"item\": \"laptop\", \"quantity\": 5, \"budget\": 50000.0}}"),
    ("human", "{email}")
])

email_parser = JsonOutputParser()


def email_agent(email_text: str) -> PurchaseRequest:
    print("📨 EmailAgent (LLM) çalıştı")

    chain = email_prompt | llm | email_parser
    data = chain.invoke({"email": email_text})

    return PurchaseRequest(
        item=data["item"],
        quantity=int(data["quantity"]),
        budget=float(data["budget"])
    )


# =========================
# SUPPLIER AGENT (LLM)
# =========================


supplier_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You MUST return valid JSON.\n"
     "price_per_unit MUST be a number.\n"
     "If unsure, estimate a realistic price.\n"
     "JSON schema:\n"
     "{{\n"
     '  "name": string,\n'
     '  "price_per_unit": number,\n'
     '  "compliant": boolean\n'
     "}}"),
    ("human",
     "Item: {item}\nQuantity: {quantity}\nBudget: {budget}")
])

supplier_parser = JsonOutputParser()


def supplier_agent(request: PurchaseRequest) -> Supplier:
    print("🏭 SupplierAgent (LLM) çalıştı")

    chain = supplier_prompt | llm | supplier_parser
    data = chain.invoke({
        "item": request.item,
        "quantity": request.quantity,
        "budget": request.budget
    })

    price = data.get("price_per_unit")

    # 🔥 FAIL-SAFE
    if price is None:
        raise ValueError("SupplierAgent returned null price_per_unit")

    return Supplier(
        name=data.get("name", "Unknown Supplier"),
        price_per_unit=float(price),
        compliant=bool(data.get("compliant", False))
    )


# =========================
# COMPLIANCE AGENT (RULE-BASED)
# =========================

def compliance_agent(supplier: Supplier, request: PurchaseRequest) -> bool:
    print("📋 ComplianceAgent çalıştı")

    total_cost = supplier.price_per_unit * request.quantity

    if not supplier.compliant:
        return False

    if total_cost > request.budget:
        return False

    return True


# =========================
# ORDER AGENT
# =========================

def order_agent(supplier: Supplier, request: PurchaseRequest) -> Dict[str, Any]:
    print("🧾 OrderAgent çalıştı")

    return {
        "supplier": supplier.name,
        "item": request.item,
        "quantity": request.quantity,
        "total_price": supplier.price_per_unit * request.quantity,
        "status": "ORDER_PLACED"
    }


# =========================
# ORCHESTRATOR (BATCH)
# =========================

def orchestrator_batch(emails: List[str]) -> List[EvaluationResult]:
    results = []

    print("\n🚀 Batch Orchestrator başladı\n")

    for idx, email in enumerate(emails, start=1):
        print(f"\n--- ✉️ Email #{idx} ---")

        try:
            request = email_agent(email)
            supplier = supplier_agent(request)

            if not compliance_agent(supplier, request):
                results.append(EvaluationResult(
                    email_id=idx,
                    status="REJECTED",
                    reason="Compliance or budget violation",
                    order=None
                ))
                print("❌ Reddedildi")
                continue

            order = order_agent(supplier, request)

            results.append(EvaluationResult(
                email_id=idx,
                status="SUCCESS",
                reason=None,
                order=order
            ))
            print("✅ Başarılı")

        except Exception as e:
            results.append(EvaluationResult(
                email_id=idx,
                status="ERROR",
                reason=str(e),
                order=None
            ))
            print("🔥 Hata:", e)

    return results


# =========================
# EVALUATION
# =========================

def evaluate_results(results: List[EvaluationResult]):
    print("\n📊 TOPLU DEĞERLENDİRME\n")

    for r in results:
        print(f"Email #{r.email_id} → {r.status}")
        if r.reason:
            print("  Sebep:", r.reason)
        if r.order:
            print("  Order:", r.order)


# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":

    incoming_emails = [
        # ✅ Başarılı örnekler
        "5 adet laptop satın alınmasını rica ediyorum. Bütçe 50000 TL.",
        "10 adet telefon alınacak. Bütçe 30000 TL.",
        "3 adet monitör gerekli. Bütçe 15000 TL.",
        
        # ❌ Başarısız örnekler
        "100 adet iPhone 15 Pro alınacak. Bütçe sadece 5000 TL.",
        "50 adet sunucu istiyoruz. Bütçe 10000 TL.",
        "2 adet araba almak istiyorum. Bütçe 100000 TL."
    ]

    print(f"📧 Toplam email sayısı: {len(incoming_emails)}")  # Bu 6 göstermeli
    
    results = orchestrator_batch(incoming_emails)
    evaluate_results(results)
