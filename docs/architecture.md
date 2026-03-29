# **Arsitektur Sistem: Code Memory (mcp-code-search)**

Dokumen ini menjelaskan desain teknis dan arsitektur dari proyek Code-Memory MCP.

## **1. Ringkasan (Overview)**

Code Memory adalah layanan pencarian kode semantik lokal yang dirancang untuk diintegrasikan sebagai *tool* dalam arsitektur AI Agent (seperti Antigravity atau Claude Desktop). Layanan ini mengindeks basis kode lokal dan memungkinkan kueri bahasa alami untuk menemukan potongan kode yang relevan dengan akurasi tinggi.

## **2. Konsep Inti (Core Concepts)**

### **2.1. Smart Chunking (AST-based)**
Alih-alih memotong teks secara sembarangan berdasarkan jumlah karakter, sistem ini menggunakan *Abstract Syntax Trees* (AST) untuk memecah kode berdasarkan batas-batas logis seperti fungsi, kelas, dan metode.
- **Lokasi Kode:** `core/ast_chunker.py`
- **Manfaat:** Menjaga keutuhan konteks fungsional dalam setiap cuplikan yang diindeks.

### **2.2. Two-Stage Semantic Search**
Proses pencarian dilakukan dalam dua tahap untuk menyeimbangkan kecepatan dan akurasi:
1.  **Retrieval (Tahap 1):** Menggunakan *vector search* (ChromaDB) untuk mengambil kandidat potensial tercepat.
2.  **Reranking (Tahap 2):** Menggunakan model **Cross-Encoder** (`ms-marco-MiniLM-L-6-v2`) untuk menilai ulang kandidat teratas.
- **Lokasi Kode:** `core/searcher.py`

### **2.3. AI Cascading (Mahaguru Escalation)**
Memungkinkan agen pekerja untuk mengeskalasi tugas kompleks ke model AI yang lebih kuat (Mahaguru). Sistem mendukung dua mode:
- **Blocking (Sequential):** Worker menunggu Mahaguru selesai merespons.
- **Non-Blocking (Parallel):** Worker memicu tugas di latar belakang menggunakan `PlanningJobManager` dan melanjutkan tugas lainnya.
- **Lokasi Kode:** `core/mahaguru_client.py` & `core/job_manager.py`

### **2.4. Idempotent Indexing**
Menggunakan database state (SQLite) untuk melacak `mtime` dan `size` setiap file. File yang tidak berubah tidak akan diindeks ulang, menghemat resource secara signifikan.
- **Lokasi Kode:** `core/indexer.py`

## **3. Diagram Komponen**

```mermaid
graph TD
    subgraph "User/Agent Interaction"
        A["AI Agent / User"]
    end

    subgraph "Application Layer (main.py)"
        B("FastAPI Server") -- "Manages" --> C{"Core Services"}
        D("MCP Server") -- "Exposes Tools" --> C
    end

    subgraph "Core Services (Singleton)"
        C -- "Uses" --> E["CodeIndexer"]
        C -- "Uses" --> F["CodeSearcher"]
        C -- "Uses" --> G["ProjectWatcher"]
        C -- "Uses" --> H["MahaguruClient"]
        C -- "Uses" --> I["RuleManager"]
        C -- "Uses" --> J["TokenManager"]
        C -- "Uses" --> O["PlanningJobManager"]
    end

    subgraph "Data & Persistence Layer"
        K["ChromaDB"]
        L["SQLite State DB"]
        M["File System (Chunks)"]
    end

    A -- "HTTP Request" --> B
    A -- "MCP Tool Call" --> D

    E -- "Writes Chunks & Metadata" --> K
    E -- "Updates File State" --> L
    E -- "Writes Chunk Text" --> M

    F -- "Queries Vectors" --> K
    F -- "Reads Chunk Text" --> M

    G -- "Monitors Files" --> E

    H -- "HTTP API Call" --> N["External Mahaguru API"]

    style E fill:#cde4ff,stroke:#333,stroke-width:2px
    style F fill:#cde4ff,stroke:#333,stroke-width:2px
    style G fill:#cde4ff,stroke:#333,stroke-width:2px
    style H fill:#cde4ff,stroke:#333,stroke-width:2px
```

## **4. Detail Alur Kerja**

### **4.1. Alur Pengindeksan**

```mermaid
flowchart TD
    Start(["Event: Indexing Triggered/File Changed"]) --> CheckState{"File State Changed? <br/>(SQLite mtime/size)"}
    CheckState -- "No" --> End(["Skip File"])
    CheckState -- "Yes" --> AST["AST-based Chunking <br/>(Fungsi/Kelas)"]
    AST --> Queue["Producer Queue <br/>(Thread Pool)"]
    Queue --> Embed["Generate Embeddings <br/>(MiniLM)"]
    Embed --> Save["Penyimpanan Data"]
    Save --> Chroma["Update ChromaDB <br/>(Vector + Metadata)"]
    Save --> FileSys["Write Chunk Text <br/>(data/chunks/)"]
    Save --> SQLite["Update SQLite State <br/>(indexer_state.sqlite)"]
    Chroma --> Done(["Indexing Selesai"])
    FileSys --> Done
    SQLite --> Done
```

1. **Event:** Perubahan file dideteksi oleh `ProjectWatcher` atau perintah `index_folder`.
2. **State Check:** `CodeIndexer` memeriksa SQLite. Jika file identik (mtime/size sama), proses dilewati.
3. **Chunking:** `ASTChunker` memecah kode.
4. **Processing:** Vektor disimpan di ChromaDB, teks asli disimpan di `data/chunks/`, dan state diperbarui di SQLite.
5. **Concurrency:** Menggunakan pola *Producer-Consumer* dengan thread pool untuk efisiensi maksimal tanpa race conditions.


### **4.2. Alur Pencarian**

```mermaid
flowchart TD
    User(["User Query"]) --> Vectorize["Convert Query to Vector"]
    Vectorize --> RetStage["Stage 1: Vector Retrieval <br/>(ChromaDB)"]
    RetStage --> Filter["Apply Metadata Filters <br/>(Project/Lang/Path)"]
    Filter --> Hydrate["Hydration: Load Chunk Text <br/>(from Disk)"]
    Hydrate --> ReRankCheck{"Reranking <br/>Enabled?"}
    ReRankCheck -- "Yes" --> Model["Cross-Encoder Reranking <br/>(Stage 2)"]
    Model --> Score["Compute Relevansi Scores"]
    Score --> Sort["Sort by Score & Limit"]
    ReRankCheck -- "No" --> Sort
    Sort --> Format["Format Output + Token usage"]
    Format --> Response(["Final Search Results"])
```

1. **Query:** User memberikan input natural language.
2. **Retrieval:** ChromaDB memberikan kandidat (default 20).
3. **Reranking:** Cross-Encoder memberikan skor relevansi baru.
4. **Final Results:** Hasil diurutkan berdasarkan skor tertinggi dan dikembalikan ke user.


### **4.3. Parallel Planning Flow (Asynchronous)**

```mermaid
sequenceDiagram
    participant Worker as Worker (Kelvin)
    participant MCP as MCP Tool (Async)
    participant Registry as PlanningJobManager
    participant Guru as Mahaguru (Pro/Claude)

    Worker->>MCP: request_async_refinement(brief)
    MCP->>Registry: create_job(id, Running)
    MCP-->>Worker: Return Job ID (Immediately)
    
    rect rgb(200, 230, 255)
        Note over Worker: Worker continues other tasks (Search, Lint, Fixes)
    end

    MCP->>Guru: Await API Response
    Guru-->>MCP: Plan Delivered
    MCP->>Registry: update_job(id, Completed, result)

    Worker->>MCP: get_planning_job_result(id)
    MCP->>Registry: check_status(id)
    Registry-->>Worker: Return Completed Plan
    MCP->>Registry: pop_job(id) (Memory Cleanup)
```

1. **Trigger:** Worker mengirimkan permintaan perencanaan yang berat.
2. **Non-Blocking:** MCP tool segera mengembalikan `job_id`, membebaskan Worker untuk tugas lain.
3. **Background Processing:** Mahaguru berpikir di latar belakang. Registry (`PlanningJobManager`) melacak statusnya secara *thread-safe*.
4. **Retrieval & GC:** Worker mengambil hasil saat siap. Registry secara otomatis menghapus data dari memori (*Popping*) setelah dikonsumsi untuk mencegah kebocoran memori.


## **5. Teknologi yang Digunakan**
- **FastAPI:** Manajemen API & Lifecycle.
- **ChromaDB:** Vector store lokal.
- **SQLite3:** Persistensi state indexing.
- **Watchdog:** Monitoring file system.
- **Sentence-Transformers:** Model embedding & reranking.
