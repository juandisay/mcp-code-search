# **Panduan Pengguna (User Guide): Code Memory MCP**

Dokumen ini berisi instruksi langkah-demi-langkah untuk menyiapkan, mengonfigurasi, dan menjalankan server Code Memory.

---

## **1. Prasyarat (Prerequisites)**
- Python 3.10 atau versi yang lebih baru sudah terinstal.
- Koneksi internet (hanya untuk mengunduh model pada saat pertama kali dijalankan).

## **2. Instalasi (Installation)**

1.  **Kloning Repositori:**
    ```bash
    git clone https://github.com/your-repo/mcp-code-search.git
    cd mcp-code-search
    ```

2.  **Siapkan Virtual Environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Untuk Linux/Mac
    # Atau: venv\Scripts\activate  # Untuk Windows
    ```

3.  **Instal Dependensi:**
    ```bash
    pip install -r requirements.txt
    ```

## **3. Konfigurasi (Configuration)**

1.  **Buat File Lingkungan (.env):**
    Salin file `.env.example` menjadi `.env`.
    ```bash
    cp .env.example .env
    ```

2.  **Sesuaikan Variabel Penting:**
    Buka `.env` dan konfigurasikan hal berikut sesuai kebutuhan Anda:
    - `CHROMA_DATA_PATH`: Lokasi penyimpanan data (default: `./data`).
    - `MAHAGURU_API_KEY`: Kunci API untuk Mahaguru (jika menggunakan fitur Ai Cascading).
    - `MAHAGURU_API_URL`: URL endpoint untuk API Mahaguru.
    - `PROJECT_FOLDER_TO_INDEX`: Direktori proyek yang ingin secara otomatis diindeks saat startup.
    - `USE_RERANKER`: Atur ke `True` untuk akurasi maksimal atau `False` untuk performa tercepat (default: `True`).

## **4. Menjalankan Server (Operation)**

Server mendukung beberapa mode operasional melalui parameter baris perintah:

### **A. Mode API FastAPI (Development & Management)**
Gunakan mode ini untuk menguji endpoint HTTP secara manual atau saat melakukan pengembangan.
```bash
python main.py
```
Akses Swagger UI melalui `http://127.0.0.1:8000/docs`.

---

### **B. Mode MCP Server (Studio / Client Integration)**
Gunakan mode ini untuk mengintegrasikan server dengan asisten AI (seperti Claude Desktop atau Antigravity).
```bash
python main.py --mcp
```
Dalam mode ini, server berkomunikasi melalui `stdio` (input/output standar).

---

### **C. Mode Pengindeksan Manual (Manual Indexing)**
Gunakan mode ini untuk mengindeks direktori proyek tertentu tanpa menjalankan server penuh.
```bash
python main.py --index /direktori/proyek/anda
```

## **5. Langkah Pertama Setelah Instalasi**

1.  **Jalankan Server API:** `python main.py`.
2.  **Indeks Proyek Anda:** Kirim permintaan ke `POST /index` dengan `folder_path` proyek Anda.
3.  **Verifikasi:** Gunakan `GET /stats` untuk melihat status pengindeksan.
4.  **Uji Pencarian:** Jika sudah terintegrasi sebagai MCP, Anda bisa langsung bertanya "Bagaimana cara kerja fungsi X di proyek saya?" ke asisten AI Anda.

## **6. Troubleshooting**
- **Masalah Database Lock:** Pastikan tidak ada dua proses server yang mengakses direktori data yang sama secara bersamaan.
- **Model Download Fail:** Jika pemuatan model gagal, pastikan Anda memiliki akses internet yang stabil agar server dapat mengunduh model dari Hugging Face pada pertama kalinya.
- **Memori Berlebih:** Jika penggunaan memori terlalu tinggi, pertimbangkan untuk menonaktifkan `USE_RERANKER` di file `.env`.
