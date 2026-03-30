import asyncio

from core.mahaguru_client import mahaguru_client


async def main():
    brief = """
Review Permintaan:
1. Automated Maintenance (Garbage Collection): Menambahkan 'prune_stale_files' di CodeIndexer dan endpoint MCP/FastAPI untuk menghapus file/root yang sudah tidak ada di disk.
2. Enhanced AST Context: Memperbarui ASTChunker untuk mengekstrak 'imports' dan 'class_hierarchy' (digabung dengan ' > ') untuk setiap chunk, dan memperbarui CodeIndexer untuk menyimpannya di metadata ChromaDB.

Pertanyaan:
Bagaimana pendapat arsitektural Anda mengenai fitur-fitur ini? Apakah sudah cukup robust untuk masuk ke production? Apakah ada saran perbaikan?
"""
    try:
        from core.context_assembler import context_assembler

        relevant_files = [
            'core/ast_chunker.py',
            'core/indexer.py',
            'api/mcp_tools.py',
            'api/fastapi_routes.py'
        ]

        context = context_assembler.assemble_refinement_context(brief, relevant_files)

        response, _ = await mahaguru_client.get_refinement(
            brief,
            code_context=context
        )
        print(response)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
