from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.core.config import get_settings

class Embedder:
    def __init__(self):
        settings = get_settings()
        self.model = GoogleGenerativeAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            api_key=settings.EMBEDDING_API_KEY,
            output_dimensionality=settings.EMBEDDING_DIMENSION
        )

    def embed_text(self, text: str) -> list[float]:
        return self.model.embed_query(text)
    def embed_documents(self, documents: list[str]) -> list[list[float]]:
        return self.model.embed_documents(documents)