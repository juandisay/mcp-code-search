# **PRD: MCP Server for Code Semantic Search**

## **1. Identitas Proyek**

- **Nama Proyek:** Code-Memory MCP
- **Versi:** 1.1.0 (Development)
- **Status:** Active Development / Beta
- **Teknologi Utama:** Python, FastAPI, ChromaDB, MCP SDK, Sentence-Transformers, Tree-Sitter (AST), Cross-Encoders.

---

## **2. Pendahuluan & Latar Belakang**

Pengembang sering kali lupa detail implementasi pada proyek-proyek lama. Menggunakan LLM untuk mencari solusi di repositori lokal biasanya memakan banyak biaya token karena context window yang terbatas. **Code-Memory MCP** menyediakan cara bagi AI untuk melakukan "pencarian cerdas" di database kode lokal dan hanya mengambil cuplikan yang relevan secara efisien.

---

## **3. Tujuan Strategis**

- **Efisiensi Biaya:** Mengurangi konsumsi token dengan sistem RAG (Retrieval-Augmented Generation) lokal.
- **Privasi:** Proses _embedding_ dan pencarian dilakukan 100% di mesin lokal tanpa mengirim seluruh kode ke cloud.
- **Kecepatan:** Menemukan fungsi atau logika spesifik dalam hitungan milidetik dari ribuan baris kode.
- **AI Cascading:** Memungkinkan model AI yang lebih kecil (Worker) untuk mengeskalasi tugas kompleks ke model yang lebih cerdas (Mahaguru) dengan konteks otomatis.

---

## **4. Fitur Utama**

### **4.1. Semantic Indexing Engine**

Sistem mampu membaca file kode dan memecahnya menjadi bagian-bagian kecil (chunking) yang bermakna.

- **Support Extension:** .py, .js, .ts, .go, .java, .md, dll.
- **AST-based Smart Chunking:** Memecah kode berdasarkan struktur (misal: per fungsi atau per kelas) untuk mempertahankan konteks fungsional.
- **Exclusion Logic:** Mengabaikan folder seperti node_modules, .git, venv, dan \_\_pycache\_\_.
- **Real-time Watcher:** Mendeteksi perubahan file secara real-time dan memperbarui indeks secara otomatis.

### **4.2. Vector Storage (ChromaDB & SQLite)**

- Menggunakan ChromaDB untuk menyimpan vektor hasil embedding secara persisten.
- Menggunakan SQLite untuk manajemen _state_ pengindeksan, memastikan hanya file yang berubah yang diproses ulang (indeksasi idempoten).
- Penyimpanan teks cuplikan secara terpisah di sistem file untuk performa database yang lebih baik.

### **4.3. Two-Stage Search Architecture**

- **Retrieval:** Pencarian awal menggunakan kemiripan kosinus (ChromaDB).
- **Reranking:** Menggunakan Cross-Encoder untuk menilai ulang relevansi cuplikan terhadap kueri, memberikan hasil yang jauh lebih akurat.

### **4.4. MCP Tool Integration**

Menyediakan interface agar LLM (seperti Claude Desktop atau Antigravity) dapat memanggil fungsi berikut:

- `semantic_code_search`: Pencarian semantik dengan filter metadata dan ranking tingkat lanjut.
- `index_folder`: Memindai folder baru ke dalam database.
- `request_mahaguru_refinement`: Eskalasi tugas ke model AI tingkat tinggi dengan konteks RAG otomatis (Blocking).
- `request_async_mahaguru_refinement`: Eskalasi tugas asinkron yang memungkinkan kerja paralel (Non-Blocking).
- `get_planning_job_result`: Mengambil hasil dari tugas perencanaan asinkron.
- `sync_agent_rules`: Sinkronisasi aturan agen (.agents/rules) berdasarkan stack teknologi proyek.

---

## **Roadmap v1.1.0**

### **1. Hybrid Search (Precision Upgrade)**
- Integrasi **BM25 / Keyword Search** berdampingan dengan Vector Search.
- Menggunakan **SQLite FTS5** untuk pencarian kata kunci yang cepat.
- Rank Fusion untuk menggabungkan skor semantik dan leksikal.

### **2. Automated Maintenance (Garbage Collection)**
- Deteksi otomatis file yang dihapus melalui `maintenance/prune`.
- Sinkronisasi *idempotent* antara state database dan sistem file.

### **3. Enhanced AST Context**
- Penambahan elemen `imports` dan `class hierarchy` ke dalam metadata chunk.
- Peningkatan akurasi pengambilan untuk kode yang memiliki ketergantungan (dependencies) tinggi.

---

## **5. Arsitektur Teknis**

### **5.1. Komponen Perangkat Lunak**

1. **FastAPI Server:** API layer untuk manajemen database, statistik, dan sinkronisasi aturan.
2. **MCP Wrapper:** Implementasi protokol MCP untuk komunikasi dua arah dengan LLM.
3. **Local Embedding Model:** Menggunakan all-MiniLM-L6-v2 untuk performa CPU yang ringan.
4. **Cross-Encoder Model:** Digunakan untuk reranking hasil pencarian guna akurasi maksimal.

### **5.2. Skema Data (Metadata)**

Setiap potongan kode yang disimpan memiliki metadata lengkap:

- `file_path`: Lokasi file asli.
- `start_line`: Baris awal kode.
- `project_name`: Nama folder proyek untuk filter pencarian.
- `language`: Ekstensi file.

---

## **6. Spesifikasi Antarmuka (API & Tools)**

### **6.1. MCP Tools**

Sistem menyediakan berbagai alat untuk integrasi asisten AI:

- **`semantic_code_search`**: Parameter meliputi `query`, `n_results`, `project_name`, `language`, `re_rank`.
- **`request_mahaguru_refinement`**: Parameter meliputi `refinement_brief`, `relevant_files`. Memungkinkan eskalasi ke model cerdas dengan konteks otomatis.

### **6.2. FastAPI Endpoints (Management)**

- `POST /index`: Memicu proses pengindeksan di latar belakang.
- `GET /stats`: Menampilkan statistik koleksi dan proyek yang terindeks.
- `POST /sync-rules`: Mengelola aturan `.agents` di folder proyek.

---

## **7. Kebutuhan Non-Fungsional**

- **Keamanan:** Pembatasan akses ke folder di luar `ALLOWED_CONTEXT_ROOTS`.
- **Resource Management:** Batasan ukuran file context (100KB) dan token context (30.000 tokens) untuk mencegah penggunaan memori berlebih.
- **Skalabilitas:** Arsitektur *singleton* dan pola *producer-consumer* untuk menangani ribuan file secara efisien.

---

## **8. Status Implementasi**

Seluruh fitur inti yang disebutkan di atas telah diimplementasikan dan tersedia dalam rilis V1.0.0. Proyek ini sekarang berfungsi sebagai "pusat ingatan" untuk asisten AI yang bekerja di lingkungan repositori lokal.
