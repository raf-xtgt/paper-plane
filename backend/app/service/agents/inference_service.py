
from vertexai.language_models import TextEmbeddingModel
from vertexai.generative_models import GenerativeModel, GenerationConfig
from pydantic import BaseModel

EMBEDDING_MODEL_NAME = "text-embedding-004"
embedding_model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL_NAME)


class InferenceService:
    def __init__(self):
        self.generative_model = GenerativeModel(
            "gemini-2.0-flash"
        )

    async def _generate_structured_content(self, prompt: str, response_model: BaseModel):
        """Calls the LLM with a prompt and a JSON schema, returns a Pydantic object."""
        try:

            response = await self.generative_model.generate_content_async(
                prompt,
                generation_config=GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=response_model.model_json_schema()  # Use .model_json_schema() for Vertex
                )
            )
            # print("structured content response", response) # Optional: for debugging
            response_text = response.text.strip().replace("```json", "").replace("```", "")
            print("response text")
            print(response_text)
            return response_model.model_validate_json(response_text)
        except Exception as e:
            print(f"Error generating structured content: {e}")
            # print(f"Prompt: {prompt[:200]}...") # Optional: for debugging
            return None
