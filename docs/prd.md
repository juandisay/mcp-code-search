# **PRD: MCP Server for Code Semantic Search**

## **1\. Identitas Proyek**

- **Nama Proyek:** Code-Memory MCP
- **Versi:** 1.0.0
- **Status:** Draft / In-Development
- **Teknologi Utama:** Python, FastAPI, ChromaDB, MCP SDK, Sentence-Transformers.

---

## **2\. Pendahuluan & Latar Belakang**

Pengembang sering kali lupa detail implementasi pada proyek-proyek lama. Menggunakan LLM untuk mencari solusi di repositori lokal biasanya memakan banyak biaya token karena context window yang terbatas. **Code-Memory MCP** menyediakan cara bagi AI untuk melakukan "pencarian cerdas" di database kode lokal dan hanya mengambil cuplikan yang relevan.

---

## **3\. Tujuan Strategis**

- **Efisiensi Biaya:** Mengurangi konsumsi token dengan sistem RAG (Retrieval-Augmented Generation) lokal.
- **Privasi:** Proses _embedding_ dan pencarian dilakukan 100% di mesin lokal tanpa mengirim seluruh kode ke cloud.
- **Kecepatan:** Menemukan fungsi atau logika spesifik dalam hitungan milidetik dari ribuan baris kode.

---

## **4\. Fitur Utama**

### **4.1. Semantic Indexing Engine**

Sistem harus mampu membaca file kode dan memecahnya menjadi bagian-bagian kecil (chunking) agar bisa dipahami oleh AI.

- **Support Extension:** .py, .js, .ts, .go, .java, .md.
- **Smart Chunking:** Memecah kode berdasarkan struktur (misal: per fungsi atau per kelas) bukan sekadar jumlah karakter.
- **Exclusion Logic:** Mengabaikan folder seperti node_modules, .git, venv, dan \_\_pycache\_\_.

### **4.2. Vector Storage (ChromaDB)**

- Menggunakan ChromaDB untuk menyimpan vektor hasil embedding secara persisten di direktori lokal.
- Kemampuan untuk memperbarui indeks (Upsert) jika file kode mengalami perubahan.

### **4.3. MCP Tool Integration**

Menyediakan interface agar LLM (seperti Claude Desktop) dapat memanggil fungsi berikut:

- search_code: Mencari cuplikan kode berdasarkan deskripsi natural language.
- index_folder: Memerintahkan server untuk memindai folder baru ke dalam database.

---

## **5\. Arsitektur Teknis**

### **5.1. Komponen Perangkat Lunak**

1. **FastAPI Server:** Bertindak sebagai API layer untuk manajemen database dan pemicu indexing.
2. **MCP Wrapper:** Implementasi protokol MCP untuk komunikasi dua arah dengan LLM.
3. **Local Embedding Model:** Menggunakan all-MiniLM-L6-v2 (melalui library sentence-transformers) untuk performa CPU yang ringan.

### **5.2. Skema Data (Metadata)**

Setiap potongan kode yang disimpan harus memiliki metadata:

- file_path: Lokasi file asli.
- start_line: Baris awal kode.
- project_name: Nama folder proyek untuk filter pencarian.

---

## **6\. Spesifikasi Antarmuka (API & Tools)**

### **6.1. MCP Tool Definition**

JSON

{  
 "name": "semantic_code_search",  
 "description": "Cari potongan kode dari repositori lokal menggunakan pencarian makna (NLP).",  
 "input_schema": {  
 "type": "object",  
 "properties": {  
 "query": {  
 "type": "string",  
 "description": "Apa yang ingin dicari? Contoh: 'fungsi upload file ke S3'"  
 },  
 "n_results": {  
 "type": "integer",  
 "default": 3  
 }  
 },  
 "required": \["query"\]  
 }  
}

### **6.2. FastAPI Endpoints (Management)**

- POST /index: Menerima path folder lokal untuk mulai proses embedding.
- GET /stats: Menampilkan jumlah dokumen dan koleksi yang tersedia di ChromaDB.

---

## **7\. Kebutuhan Non-Fungsional**

- **Keamanan:** API FastAPI hanya boleh diakses dari localhost.
- **Resource:** Penggunaan RAM tidak boleh melebihi 1GB saat proses indexing berat.
- **Skalabilitas:** Mampu menangani hingga 50.000 potongan kode (chunks) tanpa penurunan performa pencarian yang signifikan.

---

## **8\. Rencana Rilis**

- **V1.0 (MVP):** Pencarian semantik dasar untuk file Python di satu folder.
- **V1.1:** Penambahan filter metadata per proyek dan dukungan multi-bahasa pemrograman.
- **V1.2:** Fitur "Auto-sync" yang mendeteksi perubahan file secara real-time (Watchdog).

**9\. Struktur Path Proyek**

Struktur path (direktori) proyek utama akan diorganisasi sebagai berikut:  
mcp-code-search/  
├── main.py \# Entry point MCP Server (FastAPI)  
├── core/  
│ ├── indexer.py \# Logic memecah kode (chunking)  
│ └── searcher.py \# Logic pencarian ke ChromaDB  
├── data/ \# Tempat database ChromaDB disimpan  
├── skills.md \# Katalog kemampuan/modul proyek  
└── requirements.txt \# Library yang dibutuhkan

Berikut adalah teks untuk ditambahkan sebagai bagian **10\. Kebutuhan (Requirements)**:

**10\. Kebutuhan (Requirements)**  
\# MCP & API  
mcp\>=0.1.0 \# SDK resmi dari Anthropic  
fastapi \# Framework API  
uvicorn \# Server untuk menjalankan FastAPI

\# Vector Database & NLP  
chromadb \# Database vektor lokal  
sentence-transformers \# Model embedding (all-MiniLM-L6-v2) lokal  
langchain-text-splitters \# Memecah kode (Python, JS, dll) dengan cerdas

\# Utilities  
pydantic \# Validasi data  
python-dotenv \# Mengelola konfigurasi/path folder

Berdasarkan dokumen **PRD: MCP Server for Code Semantic Search**, penggunaan MCP (MCP Tool Integration) difokuskan pada penyediaan antarmuka agar Model Bahasa Besar (LLM), seperti Claude Desktop, dapat berinteraksi dengan server pencarian kode semantik lokal.

Berikut adalah cara penggunaannya berdasarkan fitur yang didefinisikan:1. Interaksi dengan LLM (Tool Integration)

LLM akan memanggil fungsi-fungsi (Tools) yang terdaftar di server MCP. Fungsi utama yang disediakan adalah:

- **`search_code`**: Digunakan untuk mencari cuplikan kode yang relevan dari database lokal berdasarkan deskripsi dalam bahasa natural (natural language description).
- **`index_folder`**: Digunakan untuk memerintahkan server agar memindai folder kode baru dan menambahkannya ke dalam database vektor (ChromaDB) untuk diindeks.

2\. Detail Spesifikasi Tool: `semantic_code_search`

Tool utama yang akan digunakan LLM untuk mencari kode didefinisikan sebagai berikut:

| Properti           | Deskripsi                                                                   |
| ------------------ | --------------------------------------------------------------------------- |
| **`name`**         | `semantic_code_search`                                                      |
| **`description`**  | Cari potongan kode dari repositori lokal menggunakan pencarian makna (NLP). |
| **`input_schema`** | Skema input untuk memanggil fungsi.                                         |

**Parameter Input:**

| Parameter       | Tipe      | Diperlukan? | Deskripsi                                                       | Default |
| --------------- | --------- | ----------- | --------------------------------------------------------------- | ------- |
| **`query`**     | `string`  | Ya          | Apa yang ingin dicari? **Contoh:** `'fungsi upload file ke S3'` | \-      |
| **`n_results`** | `integer` | Tidak       | Jumlah hasil cuplikan kode yang diinginkan.                     | `3`     |

**Contoh Mekanisme Penggunaan:**

Seorang pengembang dapat mengajukan pertanyaan ke LLM (misalnya, "Bagaimana cara membuat file di Python?"), dan LLM akan secara internal mengenali pertanyaan tersebut sebagai permintaan pencarian kode. LLM kemudian akan memanggil tool `semantic_code_search` dengan mengisi parameter `query` menjadi `'fungsi membuat file di Python'`. Server MCP akan mengembalikan cuplikan kode yang paling relevan ke LLM untuk kemudian disajikan kepada pengguna.
