# 🌐 IndicTrans AI Translation API & PDF Intelligence Platform

A high-performance, multi-tenant Translation API and PDF Processing Engine powered by **AI4Bharat's IndicTrans2** neural machine translation models.

The platform provides token-quota authorization, pluggable payment & storage adapters, 200MB tenant storage limit enforcement, Auto and Manual PDF page extraction, embedded image OCR (Tesseract), language-mapped translation caching with 0-token duplicate lookups, and real-time usage analytics (REST API + Interactive Dashboard + Embeddable Widget).

---

## 🌟 Key Features

1. **AI4Bharat IndicTrans2 Neural Translation Engine**:
   - Supports 22+ Indic languages (Hindi, Marathi, Tamil, Telugu, Gujarati, Bengali, Punjabi, Kannada, Malayalam, Odia, etc.) and English.
   - Word-level token accounting (1 word = 1 token).
   - Singleton adapter with thread-safe lazy weight initialization.

2. **Tenant Token Authorization & Quota Guards**:
   - Multi-tenant architecture with API Key authentication (`sk_live_...`).
   - Token wallet management with real-time balance checks before every translation request.
   - Strict rejection with `HTTP 402 Payment Required` when tokens are depleted.

3. **Pluggable Payment Adapter (Dummy + Extensible)**:
   - Built on the Adapter pattern (`PaymentAdapterBase`).
   - Integrated `DummyPaymentAdapter` for seamless token purchasing.
   - Upon payment confirmation, instantly credits **5,000,000 (5M) tokens** to the tenant's wallet and records financial transactions.

4. **PDF Document Processing Service (200MB Limit + OCR + Image Extraction)**:
   - **200 MB Storage Quota**: Strictly enforced per tenant for PDF uploads (`HTTP 413` when exceeded).
   - **Auto Mode**: Uploads PDF, extracts all pages (1..N) immediately, scans for embedded images, runs Tesseract OCR, appends an OCR text section at the end of the page text, and saves all extracted images to media storage.
   - **Manual Mode**: Uploads PDF without immediate extraction, enabling on-demand page-by-page (`extract-page` / `next-page`) extraction.
   - **Page Retrieval**: Retrieve single page, page range `[start, end]`, or all extracted pages.
   - **Image Access**: Extracted images are stored on disk with metadata and served via public media URLs (`/media/...`) and a dedicated images API.

5. **Smart Translation Caching & Language Mapping**:
   - Tracks `(extracted_page, target_language)` translation records in the database.
   - **0-Token Re-reads**: Repeated requests for the same page and target language return the existing translation immediately with `cached: true` and **0 tokens deducted**.
   - Batch translates document pages (single, range, all) while intelligently skipping already cached pages.

6. **Analytics & Interactive Dashboard**:
   - **JSON Stats API**: `GET /api/dashboard/stats/` returning wallet balance, storage consumption, language breakdown, and transaction logs.
   - **Web Dashboard**: `GET /dashboard/` full dark-mode interface with live test consoles for raw translation, PDF upload, page extraction, and wallet top-ups.
   - **Embeddable Widget**: `GET /dashboard/widget/` standalone responsive meter widget.

---

## 🏗️ System Architecture

```
+-----------------------------------------------------------------------------------------+
|                                    CLIENT REQUESTS                                      |
|    - Headers: `X-API-KEY: sk_live_...` or `Authorization: Bearer sk_live_...`           |
|    - Web Interface: Full Analytics Dashboard & Embeddable HTML Widget                   |
+--------------------------------------------+--------------------------------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
|                                 GUARDS & AUTHENTICATION                                 |
|    - `tenant_auth_required`: Validates active API key & active tenant status            |
|    - Token Quota Guard: Validates token balance >= word count before execution          |
|    - Storage Quota Guard: Enforces 200 MB maximum total storage per tenant              |
+--------------------------------------------+--------------------------------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
|                                      SERVICES LAYER                                     |
|                                                                                         |
|  [Tenant & Billing Service]     [Payment Adapter]           [PDF Processing Service]    |
|  - Registration & API keys      - `PaymentAdapterBase`      - `StorageAdapterBase`      |
|  - Token wallet accounting      - `DummyPaymentAdapter`     - `LocalStorageAdapter`     |
|                                 - Grants 5,000,000 tokens   - Auto (all pages + OCR)    |
|                                                             - Manual (page-by-page)     |
|                                                             - Image OCR (Tesseract)     |
|                                                             - Page Image Persistence    |
|                                                                                         |
|  [Translation Engine Service]                               [Dashboard & Analytics]     |
|  - `TranslationEngineAdapter` (AI4Bharat IndicTrans2)       - JSON Stats API            |
|  - `TranslationService` (Per-word token deduction)          - Responsive HTML Dashboard |
|  - Language Mapping & Translation Caching (0 token re-read) - Embeddable Meter Widget   |
+--------------------------------------------+--------------------------------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
|                                      DATABASE MODELS                                    |
|  - `Tenant`, `ApiKey`, `PaymentTransaction`                                             |
|  - `Document`, `ExtractedPage`, `PageImage`, `TranslatedPage`, `TokenUsageLog`          |
+-----------------------------------------------------------------------------------------+
```

---

## 🚀 Getting Started & Installation

### 1. Prerequisites
- Python 3.10, 3.11, or 3.12
- MySQL Server (or SQLite)
- Tesseract OCR (optional, for image text recognition)
- PyTorch with CUDA (optional, for GPU acceleration)

### 2. Setup Virtual Environment
```bash
# Clone the repository
cd TranslationAPI

# Create and activate virtual environment
python -m venv .venv

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# On Linux/macOS:
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
pip install mysqlclient pytesseract pillow nltk
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"
```

### 4. Database Configuration
In `translationapi/settings.py`, configure your database:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'translation_api',
        'USER': 'root',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}
```

### 5. Run Migrations & Start Server
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```
The server will start at `http://127.0.0.1:8000/`.

---

## 🔑 Authentication

All protected endpoints require an active Tenant API Key. Provide it in one of three ways:

1. **HTTP Header (Recommended)**:
   ```http
   X-API-KEY: sk_live_abcdef1234567890...
   ```
2. **Authorization Header**:
   ```http
   Authorization: Bearer sk_live_abcdef1234567890...
   ```
3. **Query Parameter (For widgets/testing)**:
   ```http
   ?api_key=sk_live_abcdef1234567890...
   ```

---

## 📖 Complete API Reference

### 1. Tenant Management & Registration

#### `POST /api/tenant/register/`
Registers a new tenant and generates their primary API key.
- **Headers**: `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "name": "Acme Innovations",
    "email": "admin@acme.com",
    "password": "a-strong-password"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "Tenant registered successfully.",
    "data": {
      "tenant_id": 1,
      "name": "Acme Innovations",
      "email": "admin@acme.com",
      "token_balance": 0,
      "storage_used_mb": 0.0,
      "max_storage_mb": 200,
      "api_key": "<your-stripe-api-key-here>",
      "is_new": true
    }
  }
  ```

#### `POST /api/tenant/login/`
Authenticates a tenant with email and password and returns an API key for protected endpoints.
- **Request Body**: `{ "email": "admin@acme.com", "password": "a-strong-password" }`


#### `POST /api/tenant/api-keys/`
Generates an additional API key for the authenticated tenant.
- **Headers**: `X-API-KEY: <key>`, `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "name": "Production Server Key"
  }
  ```

#### `GET /api/tenant/me/`
Returns tenant profile, current token balance, lifetime tokens consumed, and storage quota details.
- **Headers**: `X-API-KEY: <key>`
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "data": {
      "tenant_id": 1,
      "name": "Acme Innovations",
      "email": "admin@acme.com",
      "token_balance": 5000000,
      "total_tokens_used": 1420,
      "storage_used_bytes": 1548291,
      "storage_used_mb": 1.48,
      "max_storage_mb": 200,
      "storage_percentage": 0.74,
      "is_active": true,
      "active_keys_count": 1
    }
  }
  ```

---

### 2. Payment & Token Purchasing (Dummy Adapter)

#### `POST /api/payment/checkout/`
Initiates a payment order for token package purchase.
- **Headers**: `X-API-KEY: <key>`
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "data": {
      "order_id": "ORDER-DUMMY-8B39F0A1",
      "amount": 49.99,
      "currency": "USD",
      "tokens_granted": 5000000,
      "status": "created",
      "provider": "dummy_payment_gateway",
      "checkout_url": "/api/payment/confirm/?order_id=ORDER-DUMMY-8B39F0A1"
    }
  }
  ```

#### `POST /api/payment/confirm/`
Confirms payment and immediately credits **5,000,000 tokens** to the tenant's wallet.
- **Headers**: `X-API-KEY: <key>`, `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "order_id": "ORDER-DUMMY-8B39F0A1",
    "transaction_id": "TXN-1725920000"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "Successfully credited 5,000,000 tokens to tenant Acme Innovations.",
    "data": {
      "transaction_id": "TXN-1725920000",
      "order_id": "ORDER-DUMMY-8B39F0A1",
      "amount": 49.99,
      "currency": "USD",
      "tokens_credited": 5000000,
      "new_balance": 5000000,
      "status": "completed"
    }
  }
  ```

---

### 3. Raw Text Translation

#### `POST /api/translate/raw/`
Translates plain text directly with real-time word-level token deduction.
- **Headers**: `X-API-KEY: <key>`, `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "text": "Artificial Intelligence is transforming language translation across India.",
    "source_lang": "eng_Latn",
    "target_lang": "hin_Deva"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "Text translated successfully.",
    "data": {
      "translated_text": "कृत्रिम बुद्धिमत्ता पूरे भारत में भाषा अनुवाद को बदल रही है।",
      "tokens_used": 9,
      "remaining_balance": 4999991,
      "source_lang": "eng_Latn",
      "target_lang": "hin_Deva"
    }
  }
  ```
- **Insufficient Tokens Response (402 Payment Required)**:
  ```json
  {
    "success": false,
    "error": {
      "code": "INSUFFICIENT_TOKENS",
      "message": "Insufficient tokens. Required: 50, Available: 12. Please top up your balance."
    }
  }
  ```

---

### 4. PDF Extraction, Storage & OCR

#### `POST /api/pdf/upload/`
Uploads a PDF document. Enforces the strict **200 MB storage quota** per tenant.
- **Headers**: `X-API-KEY: <key>`
- **Content-Type**: `multipart/form-data`
- **Form Parameters**:
  - `file` *(binary PDF file, required)*
  - `mode` *(string: `"auto"` or `"manual"`, default: `"auto"`)*
  - `title` *(string, optional: custom title)*
- **Modes**:
  - **`auto`**: Extracts all pages immediately, runs image OCR, saves images to media storage, and sets document status to `extracted`.
  - **`manual`**: Uploads file without full extraction; pages are extracted on demand.
- **Response (201 Created)**:
  ```json
  {
    "success": true,
    "message": "PDF uploaded successfully in auto mode.",
    "data": {
      "document_id": 1,
      "title": "Annual_Report_2026.pdf",
      "file_name": "Annual_Report_2026.pdf",
      "file_size_mb": 2.45,
      "total_pages": 12,
      "extracted_pages_count": 12,
      "extraction_mode": "auto",
      "status": "extracted",
      "tenant_storage_used_mb": 2.45,
      "tenant_max_storage_mb": 200
    }
  }
  ```

#### `GET /api/pdf/documents/`
Lists all uploaded documents for the tenant.
- **Headers**: `X-API-KEY: <key>`

#### `DELETE /api/pdf/<doc_id>/`
Deletes one tenant-owned PDF, its extracted pages, translations, and extracted image files.
- **Headers**: `X-API-KEY: <key>`

#### `DELETE /api/pdf/documents/`
Deletes all uploaded PDFs for the authenticated tenant, including pages, translations, and extracted image files.
- **Headers**: `X-API-KEY: <key>`

#### `POST /api/pdf/<doc_id>/extract-page/`
Manual extraction endpoint to extract a specific page or the next unextracted page.
- **Headers**: `X-API-KEY: <key>`, `Content-Type: application/json`
- **Request Body (Extract specific page)**:
  ```json
  { "page_number": 2 }
  ```
- **Request Body (Extract next sequential page)**:
  ```json
  {}
  ```
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "Page 2 extracted successfully.",
    "data": {
      "document_id": 1,
      "page_number": 2,
      "raw_text": "Financial Summary Q1 2026...",
      "ocr_text": "[Image 1 OCR Text]: Revenue Growth Chart...",
      "combined_text": "Financial Summary Q1 2026...\n\n--- Extracted Text (From Images via OCR) ---\n[Image 1 OCR Text]: Revenue Growth Chart...",
      "has_images": true,
      "image_count": 1,
      "images": [
        {
          "image_number": 1,
          "image_name": "page_2_img_1.png",
          "image_url": "/media/tenant_1/extracted_images/doc_1/page_2_img_1.png",
          "width": 800,
          "height": 450,
          "file_size_bytes": 104850,
          "ocr_text": "Revenue Growth Chart..."
        }
      ],
      "word_count": 340,
      "total_extracted": 2,
      "total_pages": 12
    }
  }
  ```

#### `GET /api/pdf/<doc_id>/pages/`
Retrieves extracted pages and their image URLs.
- **Headers**: `X-API-KEY: <key>`
- **Query Parameters**:
  - `?page=1` (Retrieve single page)
  - `?start=1&end=5` (Retrieve range of pages)
  - `?all=true` (Retrieve all extracted pages)

#### `GET /api/pdf/<doc_id>/images/`
Retrieves all extracted images and public media URLs for a document or specific page.
- **Headers**: `X-API-KEY: <key>`
- **Query Parameters**: `?page=1` *(optional: filter by page number)*
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "Images retrieved.",
    "data": {
      "document_id": 1,
      "count": 2,
      "images": [
        {
          "page_number": 2,
          "image_number": 1,
          "image_name": "page_2_img_1.png",
          "image_url": "/media/tenant_1/extracted_images/doc_1/page_2_img_1.png",
          "width": 800,
          "height": 450,
          "file_size_bytes": 104850,
          "ocr_text": "Revenue Growth Chart..."
        }
      ]
    }
  }
  ```

---

### 5. PDF Translation & Smart Caching

#### `POST /api/pdf/<doc_id>/translate-page/`
Translates a single extracted page.
- **Cache Check**: If `(page, target_lang)` was already translated, returns cached translation with `cached: true` and **0 tokens deducted**.
- **Headers**: `X-API-KEY: <key>`, `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "page_number": 1,
    "target_lang": "hin_Deva",
    "source_lang": "eng_Latn"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "Page translation completed.",
    "data": {
      "document_id": 1,
      "page_number": 1,
      "source_lang": "eng_Latn",
      "target_lang": "hin_Deva",
      "translated_text": "यह वार्षिक रिपोर्ट पृष्ठ एक है...",
      "tokens_used": 150,
      "cached": false,
      "remaining_balance": 4999850
    }
  }
  ```

#### `POST /api/pdf/<doc_id>/translate-all/`
Batch translates all extracted pages of a document, automatically reusing cached translations without double-billing.
- **Headers**: `X-API-KEY: <key>`, `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "target_lang": "hin_Deva",
    "source_lang": "eng_Latn"
  }
  ```

#### `POST /api/pdf/<doc_id>/translate-range/`
Translates a slice of pages `[start_page, end_page]`.
- **Headers**: `X-API-KEY: <key>`, `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "start_page": 1,
    "end_page": 5,
    "target_lang": "hin_Deva"
  }
  ```

#### `GET /api/pdf/<doc_id>/translations/`
Retrieves stored translated pages for any target language.
- **Headers**: `X-API-KEY: <key>`
- **Query Parameters**:
  - `?lang=hin_Deva&page=1` (Single page)
  - `?lang=hin_Deva&start=1&end=5` (Range)
  - `?lang=hin_Deva&all=true` (All translations)

---

### 6. Analytics & Dashboard

#### `GET /api/dashboard/stats/`
Returns JSON analytics for tenant metrics.
- **Headers**: `X-API-KEY: <key>`
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "data": {
      "tenant": { "id": 1, "name": "Acme Innovations", "email": "admin@acme.com" },
      "tokens": {
        "balance": 4999850,
        "total_used": 150,
        "used_today": 150,
        "used_7_days": 150
      },
      "storage": {
        "used_bytes": 2569011,
        "used_mb": 2.45,
        "max_mb": 200,
        "percentage": 1.23,
        "total_documents": 1
      },
      "activity": {
        "extracted_pages_count": 12,
        "translated_pages_count": 1,
        "language_distribution": [
          { "target_language": "hin_Deva", "count": 1, "total_tokens": 150 }
        ],
        "recent_logs": [ ... ]
      }
    }
  }
  ```

#### `GET /dashboard/` (or root `GET /`)
Interactive HTML Dashboard with dark glassmorphism theme, test consoles, PDF upload, and token purchase buttons.

#### `GET /dashboard/widget/`
Compact embeddable HTML meter widget suitable for iframes or client dashboards.

---

## 🗺️ Supported Flores Language Codes

| Language | Flores Code | Script |
|---|---|---|
| **English** | `eng_Latn` | Latin |
| **Hindi** | `hin_Deva` | Devanagari |
| **Marathi** | `mar_Deva` | Devanagari |
| **Tamil** | `tam_Taml` | Tamil |
| **Telugu** | `tel_Telu` | Telugu |
| **Gujarati** | `guj_Gujr` | Gujarati |
| **Bengali** | `ben_Beng` | Bengali |
| **Kannada** | `kan_Knda` | Kannada |
| **Malayalam**| `mal_Mlym` | Malayalam |
| **Punjabi** | `pan_Guru` | Gurmukhi |
| **Odia** | `ory_Orya` | Odia |
| **Urdu** | `urd_Arab` | Perso-Arabic |
| **Assamese** | `asm_Beng` | Bengali |
| **Sanskrit** | `san_Deva` | Devanagari |
| **Nepali** | `npi_Deva` | Devanagari |
| **Maithili** | `mai_Deva` | Devanagari |
| **Bhojpuri** | `bho_Deva` | Devanagari |

---

## 🧪 Running Automated Tests

Run the complete test suite:
```bash
python manage.py test
```

---

## 📄 License
This project is licensed under the MIT License. IndicTrans2 models are provided by AI4Bharat under the CC-BY-4.0 license.# 🌐 IndicTrans AI Translation API & PDF Intelligence Platform

A high-performance, multi-tenant Translation API and PDF Processing Engine powered by **AI4Bharat's IndicTrans2** neural machine translation models.

The platform provides token-quota authorization, pluggable payment & storage adapters, 200MB tenant storage limit enforcement, Auto and Manual PDF page extraction, embedded image OCR (Tesseract), language-mapped translation caching with 0-token duplicate lookups, and real-time usage analytics (REST API + Interactive Dashboard + Embeddable Widget).

---

## 🌟 Key Features

1. **AI4Bharat IndicTrans2 Neural Translation Engine**:
   - Supports 22+ Indic languages (Hindi, Marathi, Tamil, Telugu, Gujarati, Bengali, Punjabi, Kannada, Malayalam, Odia, etc.) and English.
   - Word-level token accounting (1 word = 1 token).
   - Singleton adapter with thread-safe lazy weight initialization.

2. **Tenant Token Authorization & Quota Guards**:
   - Multi-tenant architecture with API Key authentication (`sk_live_...`).
   - Token wallet management with real-time balance checks before every translation request.
   - Strict rejection with `HTTP 402 Payment Required` when tokens are depleted.

3. **Pluggable Payment Adapter (Dummy + Extensible)**:
   - Built on the Adapter pattern (`PaymentAdapterBase`).
   - Integrated `DummyPaymentAdapter` for seamless token purchasing.
   - Upon payment confirmation, instantly credits **5,000,000 (5M) tokens** to the tenant's wallet and records financial transactions.

4. **PDF Document Processing Service (200MB Limit + OCR + Image Extraction)**:
   - **200 MB Storage Quota**: Strictly enforced per tenant for PDF uploads (`HTTP 413` when exceeded).
   - **Auto Mode**: Uploads PDF, extracts all pages (1..N) immediately, scans for embedded images, runs Tesseract OCR, appends an OCR text section at the end of the page text, and saves all extracted images to media storage.
   - **Manual Mode**: Uploads PDF without immediate extraction, enabling on-demand page-by-page (`extract-page` / `next-page`) extraction.
   - **Page Retrieval**: Retrieve single page, page range `[start, end]`, or all extracted pages.
   - **Image Access**: Extracted images are stored on disk with metadata and served via public media URLs (`/media/...`) and a dedicated images API.

5. **Smart Translation Caching & Language Mapping**:
   - Tracks `(extracted_page, target_language)` translation records in the database.
   - **0-Token Re-reads**: Repeated requests for the same page and target language return the existing translation immediately with `cached: true` and **0 tokens deducted**.
   - Batch translates document pages (single, range, all) while intelligently skipping already cached pages.

6. **Analytics & Interactive Dashboard**:
   - **JSON Stats API**: `GET /api/dashboard/stats/` returning wallet balance, storage consumption, language breakdown, and transaction logs.
   - **Web Dashboard**: `GET /dashboard/` full dark-mode interface with live test consoles for raw translation, PDF upload, page extraction, and wallet top-ups.
   - **Embeddable Widget**: `GET /dashboard/widget/` standalone responsive meter widget.

---

## 🏗️ System Architecture

```
+-----------------------------------------------------------------------------------------+
|                                    CLIENT REQUESTS                                      |
|    - Headers: `X-API-KEY: sk_live_...` or `Authorization: Bearer sk_live_...`           |
|    - Web Interface: Full Analytics Dashboard & Embeddable HTML Widget                   |
+--------------------------------------------+--------------------------------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
|                                 GUARDS & AUTHENTICATION                                 |
|    - `tenant_auth_required`: Validates active API key & active tenant status            |
|    - Token Quota Guard: Validates token balance >= word count before execution          |
|    - Storage Quota Guard: Enforces 200 MB maximum total storage per tenant              |
+--------------------------------------------+--------------------------------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
|                                      SERVICES LAYER                                     |
|                                                                                         |
|  [Tenant & Billing Service]     [Payment Adapter]           [PDF Processing Service]    |
|  - Registration & API keys      - `PaymentAdapterBase`      - `StorageAdapterBase`      |
|  - Token wallet accounting      - `DummyPaymentAdapter`     - `LocalStorageAdapter`     |
|                                 - Grants 5,000,000 tokens   - Auto (all pages + OCR)    |
|                                                             - Manual (page-by-page)     |
|                                                             - Image OCR (Tesseract)     |
|                                                             - Page Image Persistence    |
|                                                                                         |
|  [Translation Engine Service]                               [Dashboard & Analytics]     |
|  - `TranslationEngineAdapter` (AI4Bharat IndicTrans2)       - JSON Stats API            |
|  - `TranslationService` (Per-word token deduction)          - Responsive HTML Dashboard |
|  - Language Mapping & Translation Caching (0 token re-read) - Embeddable Meter Widget   |
+--------------------------------------------+--------------------------------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
|                                      DATABASE MODELS                                    |
|  - `Tenant`, `ApiKey`, `PaymentTransaction`                                             |
|  - `Document`, `ExtractedPage`, `PageImage`, `TranslatedPage`, `TokenUsageLog`          |
+-----------------------------------------------------------------------------------------+
```

---

## 🚀 Getting Started & Installation

### 1. Prerequisites
- Python 3.10, 3.11, or 3.12
- MySQL Server (or SQLite)
- Tesseract OCR (optional, for image text recognition)
- PyTorch with CUDA (optional, for GPU acceleration)

### 2. Setup Virtual Environment
```bash
# Clone the repository
cd TranslationAPI

# Create and activate virtual environment
python -m venv .venv

# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# On Linux/macOS:
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
pip install mysqlclient pytesseract pillow nltk
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"
```

### 4. Database Configuration
In `translationapi/settings.py`, configure your database:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'translation_api',
        'USER': 'root',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}
```

### 5. Run Migrations & Start Server
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```
The server will start at `http://127.0.0.1:8000/`.

---

## 🔑 Authentication

All protected endpoints require an active Tenant API Key. Provide it in one of three ways:

1. **HTTP Header (Recommended)**:
   ```http
   X-API-KEY: sk_live_abcdef1234567890...
   ```
2. **Authorization Header**:
   ```http
   Authorization: Bearer sk_live_abcdef1234567890...
   ```
3. **Query Parameter (For widgets/testing)**:
   ```http
   ?api_key=sk_live_abcdef1234567890...
   ```

---

## 📖 Complete API Reference

### 1. Tenant Management & Registration

#### `POST /api/tenant/register/`
Registers a new tenant and generates their primary API key.
- **Headers**: `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "name": "Acme Innovations",
    "email": "admin@acme.com",
    "password": "a-strong-password"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "Tenant registered successfully.",
    "data": {
      "tenant_id": 1,
      "name": "Acme Innovations",
      "email": "admin@acme.com",
      "token_balance": 0,
      "storage_used_mb": 0.0,
      "max_storage_mb": 200,
      "api_key": "<your-stripe-api-key-here>",
      "is_new": true
    }
  }
  ```

#### `POST /api/tenant/login/`
Authenticates a tenant with email and password and returns an API key for protected endpoints.
- **Request Body**: `{ "email": "admin@acme.com", "password": "a-strong-password" }`


#### `POST /api/tenant/api-keys/`
Generates an additional API key for the authenticated tenant.
- **Headers**: `X-API-KEY: <key>`, `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "name": "Production Server Key"
  }
  ```

#### `GET /api/tenant/me/`
Returns tenant profile, current token balance, lifetime tokens consumed, and storage quota details.
- **Headers**: `X-API-KEY: <key>`
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "data": {
      "tenant_id": 1,
      "name": "Acme Innovations",
      "email": "admin@acme.com",
      "token_balance": 5000000,
      "total_tokens_used": 1420,
      "storage_used_bytes": 1548291,
      "storage_used_mb": 1.48,
      "max_storage_mb": 200,
      "storage_percentage": 0.74,
      "is_active": true,
      "active_keys_count": 1
    }
  }
  ```

---

### 2. Payment & Token Purchasing (Dummy Adapter)

#### `POST /api/payment/checkout/`
Initiates a payment order for token package purchase.
- **Headers**: `X-API-KEY: <key>`
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "data": {
      "order_id": "ORDER-DUMMY-8B39F0A1",
      "amount": 49.99,
      "currency": "USD",
      "tokens_granted": 5000000,
      "status": "created",
      "provider": "dummy_payment_gateway",
      "checkout_url": "/api/payment/confirm/?order_id=ORDER-DUMMY-8B39F0A1"
    }
  }
  ```

#### `POST /api/payment/confirm/`
Confirms payment and immediately credits **5,000,000 tokens** to the tenant's wallet.
- **Headers**: `X-API-KEY: <key>`, `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "order_id": "ORDER-DUMMY-8B39F0A1",
    "transaction_id": "TXN-1725920000"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "Successfully credited 5,000,000 tokens to tenant Acme Innovations.",
    "data": {
      "transaction_id": "TXN-1725920000",
      "order_id": "ORDER-DUMMY-8B39F0A1",
      "amount": 49.99,
      "currency": "USD",
      "tokens_credited": 5000000,
      "new_balance": 5000000,
      "status": "completed"
    }
  }
  ```

---

### 3. Raw Text Translation

#### `POST /api/translate/raw/`
Translates plain text directly with real-time word-level token deduction.
- **Headers**: `X-API-KEY: <key>`, `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "text": "Artificial Intelligence is transforming language translation across India.",
    "source_lang": "eng_Latn",
    "target_lang": "hin_Deva"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "Text translated successfully.",
    "data": {
      "translated_text": "कृत्रिम बुद्धिमत्ता पूरे भारत में भाषा अनुवाद को बदल रही है।",
      "tokens_used": 9,
      "remaining_balance": 4999991,
      "source_lang": "eng_Latn",
      "target_lang": "hin_Deva"
    }
  }
  ```
- **Insufficient Tokens Response (402 Payment Required)**:
  ```json
  {
    "success": false,
    "error": {
      "code": "INSUFFICIENT_TOKENS",
      "message": "Insufficient tokens. Required: 50, Available: 12. Please top up your balance."
    }
  }
  ```

---

### 4. PDF Extraction, Storage & OCR

#### `POST /api/pdf/upload/`
Uploads a PDF document. Enforces the strict **200 MB storage quota** per tenant.
- **Headers**: `X-API-KEY: <key>`
- **Content-Type**: `multipart/form-data`
- **Form Parameters**:
  - `file` *(binary PDF file, required)*
  - `mode` *(string: `"auto"` or `"manual"`, default: `"auto"`)*
  - `title` *(string, optional: custom title)*
- **Modes**:
  - **`auto`**: Extracts all pages immediately, runs image OCR, saves images to media storage, and sets document status to `extracted`.
  - **`manual`**: Uploads file without full extraction; pages are extracted on demand.
- **Response (201 Created)**:
  ```json
  {
    "success": true,
    "message": "PDF uploaded successfully in auto mode.",
    "data": {
      "document_id": 1,
      "title": "Annual_Report_2026.pdf",
      "file_name": "Annual_Report_2026.pdf",
      "file_size_mb": 2.45,
      "total_pages": 12,
      "extracted_pages_count": 12,
      "extraction_mode": "auto",
      "status": "extracted",
      "tenant_storage_used_mb": 2.45,
      "tenant_max_storage_mb": 200
    }
  }
  ```

#### `GET /api/pdf/documents/`
Lists all uploaded documents for the tenant.
- **Headers**: `X-API-KEY: <key>`

#### `DELETE /api/pdf/<doc_id>/`
Deletes one tenant-owned PDF, its extracted pages, translations, and extracted image files.
- **Headers**: `X-API-KEY: <key>`

#### `DELETE /api/pdf/documents/`
Deletes all uploaded PDFs for the authenticated tenant, including pages, translations, and extracted image files.
- **Headers**: `X-API-KEY: <key>`

#### `POST /api/pdf/<doc_id>/extract-page/`
Manual extraction endpoint to extract a specific page or the next unextracted page.
- **Headers**: `X-API-KEY: <key>`, `Content-Type: application/json`
- **Request Body (Extract specific page)**:
  ```json
  { "page_number": 2 }
  ```
- **Request Body (Extract next sequential page)**:
  ```json
  {}
  ```
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "Page 2 extracted successfully.",
    "data": {
      "document_id": 1,
      "page_number": 2,
      "raw_text": "Financial Summary Q1 2026...",
      "ocr_text": "[Image 1 OCR Text]: Revenue Growth Chart...",
      "combined_text": "Financial Summary Q1 2026...\n\n--- Extracted Text (From Images via OCR) ---\n[Image 1 OCR Text]: Revenue Growth Chart...",
      "has_images": true,
      "image_count": 1,
      "images": [
        {
          "image_number": 1,
          "image_name": "page_2_img_1.png",
          "image_url": "/media/tenant_1/extracted_images/doc_1/page_2_img_1.png",
          "width": 800,
          "height": 450,
          "file_size_bytes": 104850,
          "ocr_text": "Revenue Growth Chart..."
        }
      ],
      "word_count": 340,
      "total_extracted": 2,
      "total_pages": 12
    }
  }
  ```

#### `GET /api/pdf/<doc_id>/pages/`
Retrieves extracted pages and their image URLs.
- **Headers**: `X-API-KEY: <key>`
- **Query Parameters**:
  - `?page=1` (Retrieve single page)
  - `?start=1&end=5` (Retrieve range of pages)
  - `?all=true` (Retrieve all extracted pages)

#### `GET /api/pdf/<doc_id>/images/`
Retrieves all extracted images and public media URLs for a document or specific page.
- **Headers**: `X-API-KEY: <key>`
- **Query Parameters**: `?page=1` *(optional: filter by page number)*
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "Images retrieved.",
    "data": {
      "document_id": 1,
      "count": 2,
      "images": [
        {
          "page_number": 2,
          "image_number": 1,
          "image_name": "page_2_img_1.png",
          "image_url": "/media/tenant_1/extracted_images/doc_1/page_2_img_1.png",
          "width": 800,
          "height": 450,
          "file_size_bytes": 104850,
          "ocr_text": "Revenue Growth Chart..."
        }
      ]
    }
  }
  ```

---

### 5. PDF Translation & Smart Caching

#### `POST /api/pdf/<doc_id>/translate-page/`
Translates a single extracted page.
- **Cache Check**: If `(page, target_lang)` was already translated, returns cached translation with `cached: true` and **0 tokens deducted**.
- **Headers**: `X-API-KEY: <key>`, `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "page_number": 1,
    "target_lang": "hin_Deva",
    "source_lang": "eng_Latn"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "Page translation completed.",
    "data": {
      "document_id": 1,
      "page_number": 1,
      "source_lang": "eng_Latn",
      "target_lang": "hin_Deva",
      "translated_text": "यह वार्षिक रिपोर्ट पृष्ठ एक है...",
      "tokens_used": 150,
      "cached": false,
      "remaining_balance": 4999850
    }
  }
  ```

#### `POST /api/pdf/<doc_id>/translate-all/`
Batch translates all extracted pages of a document, automatically reusing cached translations without double-billing.
- **Headers**: `X-API-KEY: <key>`, `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "target_lang": "hin_Deva",
    "source_lang": "eng_Latn"
  }
  ```

#### `POST /api/pdf/<doc_id>/translate-range/`
Translates a slice of pages `[start_page, end_page]`.
- **Headers**: `X-API-KEY: <key>`, `Content-Type: application/json`
- **Request Body**:
  ```json
  {
    "start_page": 1,
    "end_page": 5,
    "target_lang": "hin_Deva"
  }
  ```

#### `GET /api/pdf/<doc_id>/translations/`
Retrieves stored translated pages for any target language.
- **Headers**: `X-API-KEY: <key>`
- **Query Parameters**:
  - `?lang=hin_Deva&page=1` (Single page)
  - `?lang=hin_Deva&start=1&end=5` (Range)
  - `?lang=hin_Deva&all=true` (All translations)

---

### 6. Analytics & Dashboard

#### `GET /api/dashboard/stats/`
Returns JSON analytics for tenant metrics.
- **Headers**: `X-API-KEY: <key>`
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "data": {
      "tenant": { "id": 1, "name": "Acme Innovations", "email": "admin@acme.com" },
      "tokens": {
        "balance": 4999850,
        "total_used": 150,
        "used_today": 150,
        "used_7_days": 150
      },
      "storage": {
        "used_bytes": 2569011,
        "used_mb": 2.45,
        "max_mb": 200,
        "percentage": 1.23,
        "total_documents": 1
      },
      "activity": {
        "extracted_pages_count": 12,
        "translated_pages_count": 1,
        "language_distribution": [
          { "target_language": "hin_Deva", "count": 1, "total_tokens": 150 }
        ],
        "recent_logs": [ ... ]
      }
    }
  }
  ```

#### `GET /dashboard/` (or root `GET /`)
Interactive HTML Dashboard with dark glassmorphism theme, test consoles, PDF upload, and token purchase buttons.

#### `GET /dashboard/widget/`
Compact embeddable HTML meter widget suitable for iframes or client dashboards.

---

## 🗺️ Supported Flores Language Codes

| Language | Flores Code | Script |
|---|---|---|
| **English** | `eng_Latn` | Latin |
| **Hindi** | `hin_Deva` | Devanagari |
| **Marathi** | `mar_Deva` | Devanagari |
| **Tamil** | `tam_Taml` | Tamil |
| **Telugu** | `tel_Telu` | Telugu |
| **Gujarati** | `guj_Gujr` | Gujarati |
| **Bengali** | `ben_Beng` | Bengali |
| **Kannada** | `kan_Knda` | Kannada |
| **Malayalam**| `mal_Mlym` | Malayalam |
| **Punjabi** | `pan_Guru` | Gurmukhi |
| **Odia** | `ory_Orya` | Odia |
| **Urdu** | `urd_Arab` | Perso-Arabic |
| **Assamese** | `asm_Beng` | Bengali |
| **Sanskrit** | `san_Deva` | Devanagari |
| **Nepali** | `npi_Deva` | Devanagari |
| **Maithili** | `mai_Deva` | Devanagari |
| **Bhojpuri** | `bho_Deva` | Devanagari |

---

## 🧪 Running Automated Tests

Run the complete test suite:
```bash
python manage.py test
```

---

## 📄 License
This project is licensed under the MIT License. IndicTrans2 models are provided by AI4Bharat under the CC-BY-4.0 license.