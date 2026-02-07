# 🤖 Multi-Agent Procurement System

Gayrimenkul şirketi satın alma süreçlerini otomatikleştiren LangChain ve Ollama tabanlı çok-ajanlı sistem. E-posta ile gelen satın alma taleplerini otomatik olarak işler, tedarikçi bulur, uygunluk kontrolü yapar ve sipariş oluşturur.

## 📋 Problem

Greypine gibi gayrimenkul şirketlerinde satın alma yöneticileri şu süreçlerle uğraşır:
- 📧 E-postalardaki satın alma taleplerini inceleme
- 🏭 Uygun tedarikçileri belirleme
- 📋 Tedarikçilerin şirket politikalarına uygunluğunu kontrol etme
- 💰 Bütçe kontrolü ve sipariş finalizasyonu

**Sorun**: Sürekli farklı uygulamalar arasında geçiş yapmak verimsizlik yaratır.

**Çözüm**: Çok-ajanlı otomasyon sistemi tüm süreci koordine eder.

## 🏗️ Multi-Agent Mimari

Bu proje **Cooperative Multiagent System** (İşbirlikçi Çok-Ajanlı Sistem) mimarisini kullanır.

### Sistem Tipi: Cooperative + Hierarchical
```
ORCHESTRATOR (Yönetici)
    ↓
Email Agent (LLM) → Supplier Agent (LLM) → Compliance Agent (Rule) → Order Agent (Rule)
    ↓                    ↓                        ↓                       ↓
Veri Çıkar          Tedarikçi Bul           Kontrol Et              Sipariş Oluştur
```

**Neden Cooperative?**
- ✅ Tüm ajanlar ortak hedefe çalışır: Satın alma sürecini tamamlamak
- ✅ Her ajan bir sonrakine bilgi aktarır
- ✅ Rekabet yok, sadece koordinasyon var
- ✅ Bir ajanın başarısı tüm sistemi başarıya götürür

**Hierarchical Özellikler:**
- 🎯 Orchestrator tüm ajanları koordine eder
- 🎯 Belirli bir iş akışı sırası vardır
- 🎯 Her ajan kendi sorumluluğuna odaklanır

### 4 Ajan:

**1. Email Agent** (LLM-based)
- **Görev**: E-postalardan satın alma talebini çıkarır
- **Teknoloji**: LangChain + Ollama
- **Çıktı**: `PurchaseRequest(item, quantity, budget)`

**2. Supplier Agent** (LLM-based)
- **Görev**: Uygun tedarikçi bulur ve fiyat belirler
- **Özellik**: Gerçekçi piyasa fiyatları tahmin eder
- **Çıktı**: `Supplier(name, price_per_unit, compliant)`

**3. Compliance Agent** (Rule-based)
- **Görev**: Şirket politikası ve bütçe kontrolü yapar
- **Kontroller**: Tedarikçi uygunluğu, bütçe limiti
- **Çıktı**: `True/False`

**4. Order Agent** (Rule-based)
- **Görev**: Onaylanan siparişi oluşturur
- **Çıktı**: Sipariş detayları

**Orchestrator**: Toplu işlem yapar, hata yönetimi sağlar, sonuçları raporlar

## ✨ Özellikler

- 📧 E-postalardan otomatik satın alma talebi çıkarma
- 🏭 Tedarikçi bulma ve fiyat belirleme
- 📋 Uygunluk ve bütçe kontrolü
- 🧾 Otomatik sipariş oluşturma
- 🔄 Toplu (batch) işlem desteği
- 🤖 Yerel LLM kullanımı (Ollama)
- ⚡ Manuel müdahale olmadan hızlı ve doğru işlem

## 🚀 Kurulum

### Gereksinimler

- Python 3.10+
- Ollama (yerel LLM için - Bunun dışında API key ile istenilen GPT modeline bağlanılabilir)
- uv veya pip (paket yöneticisi)

### 1. UV ile (Önerilen)
```bash
# UV kur
curl -LsSf https://astral.sh/uv/install.sh | sh

# Proje dizinine git
cd multiagent-procurement

# Sanal ortam oluştur ve aktif et
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Bağımlılıkları yükle
uv pip install -r requirements.txt
```

### 2. Ollama Kurulumu
```bash
# Ollama indir ve kur
# https://ollama.ai

# Model indir
ollama pull <Model Name>
```

## 💻 Kullanım
```bash
python multiagent_procurement_langchain.py
```


## 🔄 Sistem Akışı

1. **E-posta Girişi**: Satın alma talepleri batch olarak sisteme gelir
2. **Email Agent**: LLM ile yapılandırılmış veri çıkarımı (`item`, `quantity`, `budget`)
3. **Supplier Agent**: LLM ile tedarikçi ve fiyat belirleme
4. **Compliance Check**: Kural tabanlı kontrol
   - ❌ Tedarikçi uygunsuz veya bütçe aşımı → `REJECTED`
   - ✅ Her şey uygun → Sipariş oluştur
5. **Order Agent**: Sipariş detaylarını oluştur
6. **Sonuç**: Başarı/Red/Hata raporu

## 🎯 Kullanım Senaryoları

### Senaryo 1: Başarılı Sipariş
```python
incoming_emails = [
    "5 adet laptop satın alınmasını rica ediyorum. Bütçe 50000 TL."
]
# Sonuç: SUCCESS - Laptop siparişi oluşturuldu
```

### Senaryo 2: Bütçe Aşımı
```python
incoming_emails = [
    "100 adet iPhone 15 Pro alınacak. Bütçe sadece 5000 TL."
]
# Sonuç: REJECTED - Bütçe yetersiz
```

### Senaryo 3: Toplu İşlem
```python
incoming_emails = [
    "5 adet laptop satın alınmasını rica ediyorum. Bütçe 50000 TL.",
    "10 adet telefon alınacak. Bütçe 30000 TL.",
    "3 adet monitör gerekli. Bütçe 15000 TL."
]
# Sonuç: Her email için ayrı değerlendirme
```

## 📊 Multiagent System Avantajları

### Accuracy (Doğruluk)
Birden fazla ajan çapraz doğrulama yaparak hata oranını azaltır.

### Adaptability (Uyum)
Her ajan gerçek zamanlı geri bildirime göre stratejisini ayarlar.

### Scalability (Ölçeklenebilirlik)
İş yükü birden fazla ajana dağıtılarak büyük görevler verimli şekilde işlenir.

## 🐛 Bilinen Sorunlar

- Küçük LLM modelleri (3b) bazen gerçekçi olmayan fiyatlar üretebilir
- JSON parsing hataları için güvenli kontroller eklenmiştir
- LLM çıktıları deterministik değildir, aynı girdi farklı sonuçlar üretebilir

## 📚 Kaynaklar

- [LangChain Documentation](https://python.langchain.com/)
- [Ollama](https://ollama.ai)
- [UV Package Manager](https://github.com/astral-sh/uv)
- [Multiagent Systems - IBM](https://www.ibm.com/think/topics/multiagent-system)

## 🤝 Katkıda Bulunma

1. Fork yapın
2. Feature branch oluşturun (`git checkout -b feature/amazing`)
3. Commit yapın (`git commit -m 'Add amazing feature'`)
4. Push edin (`git push origin feature/amazing`)
5. Pull Request açın
