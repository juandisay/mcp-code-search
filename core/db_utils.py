from typing import Any


def get_collection_name(embedding_fn: Any) -> str:
    """Generates a consistent, model-aware collection name.
    
    This ensures that both CodeIndexer and CodeSearcher target the same 
    collection when using the same embedding function/model.
    """
    model_name = "default"

    # Check for direct attribute (common in many embedding wrappers)
    if hasattr(embedding_fn, "model_name"):
        model_name = embedding_fn.model_name
    elif hasattr(embedding_fn, "_model_name"):
        model_name = embedding_fn._model_name
    elif hasattr(embedding_fn, "__class__"):
        # Fallback to class name if no model_name is found
        model_name = embedding_fn.__class__.__name__

    # Sanitize the model name for ChromaDB (no spaces, special chars)
    safe_name = (
        model_name.replace("/", "_")
        .replace("-", "_")
        .replace(".", "_")
        .lower()
    )

    return f"code_{safe_name}"
