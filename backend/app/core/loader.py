from langchain_community.document_loaders import Docx2txtLoader

import pymupdf 


from app.controller.file_controller import FileController

def _get_links_from_pdf(page) -> list[str]:
    text_links = page.get_links()
    links = [link['uri'] for link in text_links if 'uri' in link]
    return links

def _load_pdf_with_pymupdf(file_path: str) -> list[tuple[str, dict]]:
    """Load a PDF using PyMuPDF and return page text + metadata."""
    pages: list[tuple[str, dict]] = []
    with pymupdf.open(file_path) as pdf:
        total_pages = pdf.page_count
        for page_index in range(total_pages):
            page = pdf.load_page(page_index)
            text = page.get_text("text")
            text_links = _get_links_from_pdf(page)
            text+= "\n\nLinks:\n" + "\n".join(text_links) if text_links else ""
            metadata = {
                "source": file_path,
                "page": page_index,
                "total_pages": total_pages,
                "text_links": text_links
            }
            pages.append((text, metadata))
    return pages


def load_document(file_path: str) -> dict:
    """Load a document and return its content as a dictionary."""
    file_extension = FileController.get_file_extension(file_path).lower()
    
    if file_extension == ".pdf":
        pages = _load_pdf_with_pymupdf(file_path)
    elif file_extension == ".docx":
        loader = Docx2txtLoader(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_extension}")

    if file_extension == ".pdf":
        documents = pages
    else:
        documents = loader.load()
    
    result_doc = dict()
    result_doc["content"] = []
    result_doc["metadata"] = []
    if file_extension == ".pdf":
        for page_content, metadata in documents:
            result_doc["content"].append(page_content)
            result_doc["metadata"].append(metadata)
    else:
        for doc in documents:
            result_doc["content"].append(doc.page_content)
            result_doc["metadata"].append(doc.metadata)
    return result_doc


def load_document_text(file_path: str) -> str:
    """Load a document and return its content as plain text."""
    doc = load_document(file_path)
    return " ".join(doc["content"])
    
