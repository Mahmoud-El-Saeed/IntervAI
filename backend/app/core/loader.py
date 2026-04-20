from langchain_community.document_loaders import Docx2txtLoader, PyMuPDFLoader


from app.controller.file_controller import FileController


def load_document(file_path: str) -> dict:
    """Load a document and return its content as a dictionary."""
    file_extension = FileController.get_file_extension(file_path).lower()
    
    if file_extension == ".pdf":
        loader = PyMuPDFLoader(file_path)
    elif file_extension == ".docx":
        loader = Docx2txtLoader(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_extension}")
    
    documents = loader.load()
    
    result_doc = dict()
    result_doc["content"] = []
    result_doc["metadata"] = []
    for doc in documents:
        result_doc["content"].append(doc.page_content)
        result_doc["metadata"].append(doc.metadata)
    return result_doc


def load_document_text(file_path: str) -> str:
    """Load a document and return its content as plain text."""
    doc = load_document(file_path)
    return " ".join(doc["content"])
    
