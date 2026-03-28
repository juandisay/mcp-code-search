# **Referensi API: Layanan Manajemen Code Memory**

Dokumen ini menjelaskan endpoint HTTP yang tersedia di server FastAPI untuk pengelolaan sistem Code Memory secara langsung.

## **1. Informasi Umum**
- **Base URL:** `http://127.0.0.1:8000`
- **Tujuan:** Pengelolaan administratif (monitoring, statistik, pengindeksan manual, sinkronisasi aturan).

## **2. Endpoint Referensi**

### **`POST /index`**
Memicu proses pengindeksan direktori baru di latar belakang.

- **Request Body:**
    ```json
    {
      "folder_path": "/path/to/your/project"
    }
    ```
- **Response (200 OK):**
    ```json
    {
      "message": "Indexing started in background",
      "folder_path": "/path/to/your/project"
    }
    ```
- **Contoh `curl`:**
    ```bash
    curl -X POST -H "Content-Type: application/json" \
    -d '{"folder_path": "/Users/user/my-project"}' \
    http://127.0.0.1:8000/index
    ```

---

### **`GET /health`**
Pemeriksaan status kesehatan sistem (*liveness check*).

- **Response (200 OK):**
    ```json
    {
      "status": "ok",
      "version": "1.0.0"
    }
    ```

---

### **`GET /stats`**
Mendapatkan statistik pengindeksan dan status penyimpanan saat ini.

- **Response (200 OK):**
    ```json
    {
      "total_indexed_chunks": 1450,
      "collection_name": "code_memory_default",
      "chroma_data_path": "/path/to/project/data",
      "indexed_projects": ["mcp-code-search", "my-other-project"]
    }
    ```

---

### **`DELETE /projects/{project_name}`**
Menghapus seluruh data pengindeksan yang terkait dengan nama proyek tertentu.

- **Path Parameter:** `project_name` (nama proyek, URL-encoded).
- **Response (200 OK):**
    ```json
    {
      "message": "Project deleted",
      "summary": {
        "deleted_chunks": 432,
        "deleted_files": 15
      }
    }
    ```

---

### **`POST /sync-rules`**
Mengelola sinkronisasi aturan agen (`.agents/rules`) di folder proyek target berdasarkan pendeteksian tumpukan teknologi (stack).

- **Request Body:**
    ```json
    {
      "folder_path": "/path/to/your/project",
      "context_notes": "Tambahkan aturan khusus untuk Next.js v14."
    }
    ```
- **Response (200 OK):**
    ```json
    {
      "message": "Rules synced",
      "overview": {
        "initialized": ["stack.md"],
        "updated": ["initial-workflow.md"],
        "skipped": []
      }
    }
    ```

## **3. Penanganan Kesalahan (Error Handling)**
Jika terjadi kesalahan, API akan mengembalikan kode status HTTP yang relevan (misal: 400 untuk input tidak valid atau 500 untuk kegagalan server) beserta detail kesalahannya dalam format JSON:
```json
{
  "detail": "Pesan kesalahan yang mendeskripsikan masalah."
}
```
