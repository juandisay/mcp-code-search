# **Referensi Tools MCP: Code Memory untuk AI Agent**

Dokumen ini menjelaskan daftar *tools* yang diekspos melalui server MCP, yang memungkinkan AI Agent (seperti Antigravity atau Claude) untuk berinteraksi dengan basis kode lokal secara cerdas.

## **1. Daftar Tools Utama**

### **`semantic_code_search`**
Mencari cuplikan kode menggunakan kueri bahasa alami (NLP) dengan dukungan *reranking* berbasis Cross-Encoder.

- **Parameter:**
    - `query` (str, Required): Deskripsi dari apa yang ingin dicari (contoh: "fungsi upload S3").
    - `n_results` (int, Default: 3): Jumlah hasil akhir yang diinginkan.
    - `project_name` (str, Optional): Membatasi pencarian pada proyek tertentu.
    - `language` (list[str], Optional): Membatasi pencarian pada ekstensi file tertentu (misal: `[".py", ".ts"]`).
    - `file_path_includes` (str, Optional): Filter path berbasis substring.
    - `excluded_dirs` (list[str], Optional): Direktori yang dikecualikan dari hasil pencarian.
    - `re_rank` (bool, Optional): Menentukan apakah perlu menggunakan reranking (melampaui setting default).
- **Hasil:** String terformat yang berisi lokasi file, nomor baris, dan cuplikan kode, serta skor jarak/relevansi (jika tersedia).

---

### **`index_folder`**
Memerintahkan server untuk melakukan pemindaian lengkap pada direktori proyek baru atau memperbarui indeks dalam sebuah folder.

- **Parameter:**
    - `folder_path` (str, Required): Path absolut ke direktori proyek lokal.
- **Hasil:** Ringkasan statistik (jumlah file yang diproses, dilewati, dan total potongan kode/tokens terindeks).

---

### **`list_indexed_projects`**
Menampilkan daftar seluruh nama proyek yang saat ini tersedia dalam database memori.

- **Hasil:** Daftar string nama proyek.

---

### **`delete_project`**
Menghapus sebuah proyek beserta seluruh cuplikan kodenya dari memori.

- **Parameter:**
    - `project_name` (str, Required): Nama proyek yang ingin dihapus.
- **Hasil:** Ringkasan jumlah data yang berhasil dihapus.

---

### **`get_index_stats`**
Mendapatkan statistik ringkas tentang status koleksi data yang terindeks secara keseluruhan.

- **Hasil:** Informasi tentang total potongan kode terindeks, lokasi penyimpanan, dan daftar proyek.

---

### **`sync_agent_rules`**
Versi MCP dari sinkronisasi aturan agen, digunakan untuk menginisialisasi instruksi khusus untuk asisten AI di folder proyek.

- **Parameter:**
    - `folder_path` (str, Required): Path absolut ke direktori proyek.
    - `context_notes` (str, Optional): Catatan kontekstual tambahan.
- **Hasil:** Ringkasan status sinkronisasi file aturan.

---

## **2. Fitur Eskalasi (Mahaguru)**

### **`request_mahaguru_refinement`**
Tool paling canggih yang memungkinkan AI Agent tingkat pekerja untuk mengeskalasi tugas sulit ke model "Mahaguru" (model AI yang lebih cerdas dan berkemampuan perencanaan tinggi).

- **Parameter:**
    - `refinement_brief` (str, Required): Ringkasan masalah, upaya yang telah dilakukan, dan hambatan utamanya.
    - `relevant_files` (list[str], Optional): Daftar path file konkret untuk disertakan sebagai konteks primer.
- **Mekanisme Otomatis:**
    - Sistem akan menjalankan `semantic_code_search` secara otomatis berdasarkan kueri draf tersebut untuk mengumpulkan konteks RAG pelengkap.
    - Sistem membaca isi file dalam `relevant_files` dengan pembatasan token otomatis (30k tokens max).
    - Seluruh data dikompilasi menjadi satu instruksi besar dan dikirim ke model Mahaguru.
- **Hasil:** Arahan strategis, rencana implementasi arsitektural, atau solusi perbaikan bug dari Mahaguru.
