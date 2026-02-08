from dataclasses import dataclass
from typing import List, Dict, Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import JsonOutputParser


llm = ChatOllama(
    model="qwen2.5:3b",
    temperature=0
)


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
    approval_email: Dict[str, Any] | None = None  # 👈 BURAYI EKLE


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


def compliance_agent(supplier: Supplier, request: PurchaseRequest) -> tuple[bool, str]:
    print("📋 ComplianceAgent çalıştı")

    total_cost = supplier.price_per_unit * request.quantity

    if not supplier.compliant:
        return False, "Supplier is not compliant"

    if total_cost > request.budget:
        return False, f"Budget exceeded: {total_cost} > {request.budget}"

    return True, ""  # 👈 BU SATIR VAR MI?


approval_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "You are an approval request generator. "
     "Create a professional email to request manager approval for a purchase. "
     "Return ONLY valid JSON with keys: subject, body, manager_email.\n"
     "Example:\n"
     "{{\n"
     '  "subject": "Approval Required: Laptop Purchase",\n'
     '  "body": "Dear Manager, ...",\n'
     '  "manager_email": "melisaayasak@gmail.com"\n'
     "}}"),
    ("human",
     "Item: {item}\n"
     "Quantity: {quantity}\n"
     "Supplier: {supplier}\n"
     "Unit Price: {price}\n"
     "Total Cost: {total}\n"
     "Budget: {budget}\n"
     "Reason: {reason}")
])

approval_parser = JsonOutputParser()


def approval_agent(request: PurchaseRequest, supplier: Supplier, reason: str) -> Dict[str, Any]:
    print("📧 ApprovalAgent (LLM) çalıştı - Manager'a mail hazırlanıyor")

    total = supplier.price_per_unit * request.quantity

    chain = approval_prompt | llm | approval_parser
    email_data = chain.invoke({
        "item": request.item,
        "quantity": request.quantity,
        "supplier": supplier.name,
        "price": supplier.price_per_unit,
        "total": total,
        "budget": request.budget,
        "reason": reason
    })

    return email_data


def simulate_manager_approval() -> bool:
    """
    Gerçek sistemde manager'dan cevap bekler
    Şimdilik simüle ediyoruz
    """
    import random
    # %70 ihtimalle onaylansın
    approved = random.random() < 0.7

    if approved:
        print("   ✅ Manager onayladı (simulated)")
    else:
        print("   ❌ Manager reddetti (simulated)")

    return approved


def order_agent(supplier: Supplier, request: PurchaseRequest) -> Dict[str, Any]:
    print("🧾 OrderAgent çalıştı")

    return {
        "supplier": supplier.name,
        "item": request.item,
        "quantity": request.quantity,
        "total_price": supplier.price_per_unit * request.quantity,
        "status": "ORDER_PLACED"
    }


def orchestrator_batch(emails: List[str]) -> List[EvaluationResult]:
    results = []

    print("\n🚀 Batch Orchestrator başladı\n")

    for idx, email in enumerate(emails, start=1):
        print(f"\n--- ✉️ Email #{idx} ---")

        try:
            request = email_agent(email)
            supplier = supplier_agent(request)

            # 3️⃣ Compliance kontrolü
            is_compliant, compliance_reason = compliance_agent(
                supplier, request)

            # 4️⃣ Eğer compliance fail → Approval gerekli
            if not is_compliant:
                print(f"⚠️  Compliance Issue: {compliance_reason}")
                print("📧 Approval süreci başlatılıyor...")

                # Approval maili oluştur
                approval_email = approval_agent(
                    request, supplier, compliance_reason)

                # Manager'dan onay bekle (simulated)
                manager_approved = simulate_manager_approval()

                if not manager_approved:
                    # Manager reddetti
                    results.append(EvaluationResult(
                        email_id=idx,
                        status="REJECTED_BY_MANAGER",
                        reason="Manager did not approve the request",
                        order=None,
                        approval_email=approval_email
                    ))
                    print("❌ Manager tarafından reddedildi")
                    continue

                # Manager onayladı, devam et
                print("✅ Manager onayı alındı, sipariş veriliyor...")

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


def evaluate_results(results: List[EvaluationResult]):
    print("\n" + "="*60)
    print("📊 TOPLU DEĞERLENDİRME")
    print("="*60 + "\n")

    success_count = 0
    rejected_count = 0
    error_count = 0
    approval_count = 0

    for r in results:
        print(f"📧 Email #{r.email_id} → {r.status}")

        if r.reason:
            print(f"   💬 Sebep: {r.reason}")

        if r.approval_email:
            approval_count += 1
            print(
                f"   📬 Approval Mail: {r.approval_email.get('subject', 'N/A')}")

        if r.order:
            print(f"   📦 Order: {r.order}")

        print()

        # Count
        if r.status == "SUCCESS":
            success_count += 1
        elif "REJECTED" in r.status:
            rejected_count += 1
        elif r.status == "ERROR":
            error_count += 1

    print("="*60)
    print(f"✅ Başarılı: {success_count}")
    print(f"❌ Reddedilen: {rejected_count}")
    print(f"📧 Approval gerekti: {approval_count}")
    print(f"🔥 Hata: {error_count}")
    print(f"📊 Toplam: {len(results)}")
    print("="*60)


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
