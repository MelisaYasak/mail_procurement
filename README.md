# 🏢 Greypine Procurement Assistant

> IBM watsonx Orchestrate'in AI destekli tedarik sürecini Python ile yeniden uygulayan Multi-Agent System.
LangChain, Ollama ve Streamlit kullanılarak geliştirilmiştir.

---

## 📋 Proje Hakkında

Bu proje, IBM watsonx Orchestrate'in AI destekli tedarik (procurement) sürecini Python ile yeniden uygular. Birden fazla AI agent'ın bir orchestrator tarafından koordine edildiği bir **Multi-Agent System (MAS)** mimarisine sahiptir. Kullanıcılar email gelen kutusundan başlayarak tedarikçi seçimi, uygunluk kontrolü, onay süreci ve sipariş onayına kadar tüm procurement akışını tek bir web arayüzünden yönetebilir.

---

## 🏗️ Mimari

```
┌─────────────────────────────────────────────┐
│           Streamlit Web UI                  │
│         (streamlit_procurement_v2.py)        │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│        ProcurementOrchestrator              │
│              (orchestrator.py)              │
│  - Agent registration                       │
│  - Workflow execution & coordination        │
│  - Pause / Resume mekanizması               │
│  - Error handling & logging                 │
└──────┬──────┬──────┬──────┬─────────────────┘
       │      │      │      │
       ▼      ▼      ▼      ▼
   ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
   │ 📨   │ │ 🏭   │ │ 📋   │ │ 📧   │ │ 🧾   │
   │Email │ │Supp  │ │Comp  │ │Appro │ │Order │
   │Agent │ │lier  │ │lian  │ │val   │ │Agent │
   │(LLM) │ │Agent │ │ce    │ │Agent │ │      │
   └──────┘ └──────┘ └──────┘ └──────┘ └──────┘
```
```

**Neden Cooperative?**
- ✅ Tüm agentlar ortak hedefe çalışır: satın alma sürecini tamamlamak
- ✅ Her agent bir sonrakine çıktısını input olarak aktarır
- ✅ Rekabet yok, sadece koordinasyon var

**Neden Hierarchical?**
- 🎯 Orchestrator tüm agentları merkezi olarak yönetir
- 🎯 Belirli bir iş akışı sırası ve dependency zinciri vardır
- 🎯 Her agent kendi sorumluluğuna odaklanır

---

---

## 🤖 Agentlar

| Agent | Görev | Teknoloji |
|-------|-------|-----------|
| **Email Agent** | Email'den purchase request çıkarır (item, quantity, budget) | LLM (qwen2.5:3b) |
| **Supplier Agent** | Ürün için tedarikçi listesi oluşturur | Rule-based + Random |
| **Compliance Agent** | Bütçe ve tedarikçi uygunluğunu kontrol eder | Rule-based |
| **Approval Agent** | Bütçe aşımında manager'a onay maili oluşturur | LLM (qwen2.5:3b) |
| **Order Agent** | Onaylanan siparişi tamamlar | Rule-based |

---

## 🔄 Workflow Akışı

```
1. Email Seçimi
   └─> Orchestrator.execute_workflow()
       └─> Email Agent → purchase request çıkarır
       └─> Supplier Agent → 3 tedarikçi bulur
       └─> PAUSE (kullanıcı tedarikçi seçecek)

2. Tedarikçi Seçimi
   └─> Orchestrator.resume_workflow({selected_supplier})
       └─> Compliance Agent → bütçe & uygunluk kontrolü
       └─> BUDGET OK → Order Agent → ORDER_PLACED ✅
       └─> BUDGET EXCEEDED:
           └─> Approval Agent → LLM ile manager maili oluşturur
           └─> PAUSE (manager onayı bekleniyor)

3. Manager Onayı (gerekirse)
   └─> Orchestrator.resume_workflow({manager_approved: True})
       └─> Order Agent → ORDER_PLACED ✅
```

---

## ✨ Özellikler

- ✅ **Multi-Agent System** — 5 otonom agent
- ✅ **IBM tarzı Orchestrator** — workflow koordinasyonu, pause/resume, error handling
- ✅ **Streamlit Web UI** — adım adım interaktif arayüz
- ✅ **Approval Flow** — bütçe aşımında LLM ile otomatik onay maili
- ✅ **Email Editing** — onay mailini göndermeden önce düzenleme
- ✅ **Reminder Scheduling** — otomatik hatırlatma zamanlaması
- ✅ **Process History** — tüm işlemlerin timeline log'u
- ✅ **Orchestrator Monitoring** — sidebar'da real-time execution takibi

---

## 📁 Dosya Yapısı

```
multiagent-procurement/
│
├── orchestrator.py                  # ProcurementOrchestrator class
├── streamlit_procurement_orch.py      # Ana Streamlit uygulaması
├── procurement.py                   # Batch processing versiyonu (legacy)
└── README.md
```

---

## 🚀 Kurulum

### Gereksinimler
- Python 3.11+
- [Ollama](https://ollama.ai) (lokal LLM için)
- uv (paket yöneticisi)

### 1. Ollama Kurulumu ve Model İndirme

```bash
# Ollama kur (https://ollama.ai)
ollama pull qwen2.5:3b
```

### 2. Proje Kurulumu

```bash
# git clone ile Repoyu klonla
cd multiagent-procurement

# uv ile ortam oluştur ve bağımlılıkları yükle
uv venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
uv add streamlit langchain-ollama langchain-core
```

### 3. Uygulamayı Çalıştır

```bash
# Streamlit uygulaması (önerilen)
streamlit run streamlit_procurement_orch.py

# veya batch processing versiyonu
python procurement.py
```

---

## 🖥️ Kullanım

1. **Email Inbox** — "Read and classify unread emails" butonuna tıkla
2. **Email Seç** — Procurement request emailini seç (Orchestrator otomatik başlar)
3. **Tedarikçi Seç** — Orchestrator'ın bulduğu 3 tedarikçiden birini seç
4. **Compliance** — Otomatik kontrol yapılır
   - ✅ Bütçe OK → Direkt siparişe geç
   - ⚠️ Bütçe aşımı → Approval flow başlar
5. **Approval (gerekirse)** — Maili düzenle, gönder, reminder ayarla, manager kararını simüle et
6. **Order** — Sipariş özeti ve execution summary görüntülenir

## 🛠️ Teknik Detaylar

### Orchestrator Workflow States

```python
WorkflowStatus.PENDING           # Kullanıcı kararı bekleniyor
WorkflowStatus.IN_PROGRESS       # Agent çalışıyor
WorkflowStatus.REQUIRES_APPROVAL # Manager onayı bekleniyor
WorkflowStatus.SUCCESS           # Tamamlandı
WorkflowStatus.FAILED            # Hata oluştu
```

### Agent Wrapper Yapısı

```python
def email_agent_wrapper(context: WorkflowContext, **kwargs):
    result = run_email_agent(context.email_data['body'])
    add_history("📨 Email Agent", f"Extracted: {result.item}")
    return result
```

### Orchestrator Kullanımı

```python
# Başlat
orchestrator = ProcurementOrchestrator()
orchestrator.register_agent('email_agent', email_agent_wrapper)

# Workflow çalıştır
context = orchestrator.execute_workflow(email_data)

# Devam ettir
context = orchestrator.resume_workflow(context, {'selected_supplier': supplier})

# Özet al
summary = orchestrator.get_execution_summary(context)
```

---

## 📊 Multi-Agent System Avantajları

**Accuracy (Doğruluk)**
Her agent kendi uzmanlık alanında çalışır; birden fazla kontrol katmanı hata oranını azaltır.

**Adaptability (Uyum)**
Compliance fail olduğunda sistem otomatik olarak approval flow'a geçer; manuel müdahale gerektirmez.

**Scalability (Ölçeklenebilirlik)**
Yeni bir agent eklemek için sadece `orchestrator.register_agent()` çağrısı yeterlidir; mevcut kod değişmez.

---

## 🐛 Bilinen Sorunlar

- Küçük LLM modelleri (3b) bazen gerçekçi olmayan fiyatlar üretebilir
- LLM çıktıları deterministik değildir; aynı girdi farklı sonuçlar üretebilir
- JSON parsing hataları için fail-safe kontroller eklenmiştir

---

## 📚 Kaynaklar

- [LangChain Documentation](https://python.langchain.com/)
- [Ollama](https://ollama.ai)
- [Streamlit Documentation](https://docs.streamlit.io)
- [UV Package Manager](https://github.com/astral-sh/uv)
- [IBM watsonx Orchestrate](https://www.ibm.com/products/watsonx-orchestrate)
- [Multiagent Systems — IBM](https://www.ibm.com/think/topics/multiagent-system)

---

## 🤝 Katkıda Bulunma

1. Fork yapın
2. Feature branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Commit yapın (`git commit -m 'Add amazing feature'`)
4. Push edin (`git push origin feature/amazing-feature`)
5. Pull Request açın
---

## 🙏 Teşekkür

Bu proje [IBM watsonx Orchestrate](https://www.ibm.com/products/watsonx-orchestrate) procurement demo'sundan ilham alınarak geliştirilmiştir.