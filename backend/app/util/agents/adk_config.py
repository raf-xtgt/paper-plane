"""
ADK Configuration Module

Loads and validates environment variables required for Google Agent Development Kit (ADK)
and the lead generation pipeline. Raises EnvironmentError if critical variables are missing.
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class ADKConfig:
    """Configuration class for ADK and lead generation pipeline settings"""
    
    # Google Cloud Platform Configuration
    GCP_PROJECT_ID: str
    GCP_REGION: str
    GOOGLE_APPLICATION_CREDENTIALS: str
    
    # ADK Model Configuration
    ADK_MODEL_FLASH: str
    ADK_MODEL_PRO: str
    
    # Pipeline Timeout Configuration
    LEAD_GEN_TIMEOUT: int
    RESEARCHER_TIMEOUT: int
    MAX_PARTNERS_PER_RUN: int
    
    # Optional Search API Configuration
    GOOGLE_SEARCH_API_KEY: Optional[str] = None
    GOOGLE_SEARCH_ENGINE_ID: Optional[str] = None
    DUCKDUCKGO_API_ENABLED: bool = True
    
    @classmethod
    def load(cls) -> None:
        """
        Load and validate all required environment variables.
        Raises EnvironmentError if critical variables are missing.
        """
        # Critical GCP variables
        cls.GCP_PROJECT_ID = cls._get_required_env("GCP_PROJECT_ID")
        cls.GCP_REGION = cls._get_required_env("GCP_REGION")
        cls.GOOGLE_APPLICATION_CREDENTIALS = cls._get_required_env("GOOGLE_APPLICATION_CREDENTIALS")
        
        # Validate credentials file exists
        if not os.path.exists(cls.GOOGLE_APPLICATION_CREDENTIALS):
            raise EnvironmentError(
                f"Google credentials file not found at: {cls.GOOGLE_APPLICATION_CREDENTIALS}"
            )
        
        # ADK Model Configuration
        cls.ADK_MODEL_FLASH = cls._get_required_env("ADK_MODEL_FLASH")
        cls.ADK_MODEL_PRO = cls._get_required_env("ADK_MODEL_PRO")
        
        # Pipeline Timeout Configuration
        cls.LEAD_GEN_TIMEOUT = cls._get_int_env("LEAD_GEN_TIMEOUT", default=300)
        cls.RESEARCHER_TIMEOUT = cls._get_int_env("RESEARCHER_TIMEOUT", default=30)
        cls.MAX_PARTNERS_PER_RUN = cls._get_int_env("MAX_PARTNERS_PER_RUN", default=10)
        
        # Optional Search API Configuration
        cls.GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY")
        cls.GOOGLE_SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
        cls.DUCKDUCKGO_API_ENABLED = os.getenv("DUCKDUCKGO_API_ENABLED", "true").lower() == "true"
    
    @staticmethod
    def _get_required_env(key: str) -> str:
        """
        Get required environment variable or raise EnvironmentError.
        
        Args:
            key: Environment variable name
            
        Returns:
            Environment variable value
            
        Raises:
            EnvironmentError: If variable is not set or empty
        """
        value = os.getenv(key)
        if not value:
            raise EnvironmentError(
                f"Required environment variable '{key}' is not set. "
                f"Please add it to your .env file."
            )
        return value
    
    @staticmethod
    def _get_int_env(key: str, default: int) -> int:
        """
        Get integer environment variable with default fallback.
        
        Args:
            key: Environment variable name
            default: Default value if not set or invalid
            
        Returns:
            Integer value from environment or default
        """
        value = os.getenv(key)
        if not value:
            return default
        
        try:
            return int(value)
        except ValueError:
            raise EnvironmentError(
                f"Environment variable '{key}' must be an integer, got: {value}"
            )
    
    @classmethod
    def get_vertex_ai_config(cls) -> dict:
        """
        Get Vertex AI initialization configuration.
        
        Returns:
            Dictionary with project_id and location for Vertex AI
        """
        return {
            "project": cls.GCP_PROJECT_ID,
            "location": cls.GCP_REGION
        }
    
    @classmethod
    def get_scout_config(cls) -> dict:
        """
        Get Scout Agent configuration.
        
        Returns:
            Dictionary with model name and temperature
        """
        return {
            "model": cls.ADK_MODEL_FLASH,
            "temperature": 0.3,
            "max_partners": cls.MAX_PARTNERS_PER_RUN
        }
    
    @classmethod
    def get_researcher_config(cls) -> dict:
        """
        Get Researcher Agent configuration.
        
        Returns:
            Dictionary with model name, temperature, and timeout
        """
        return {
            "model": cls.ADK_MODEL_FLASH,
            "temperature": 0.2,
            "timeout": cls.RESEARCHER_TIMEOUT
        }
    
    @classmethod
    def get_strategist_config(cls) -> dict:
        """
        Get Strategist Agent configuration.
        
        Returns:
            Dictionary with model name and temperature
        """
        return {
            "model": cls.ADK_MODEL_PRO,
            "temperature": 0.7
        }
    
    @classmethod
    def get_pipeline_config(cls) -> dict:
        """
        Get overall pipeline configuration.
        
        Returns:
            Dictionary with timeout and max partners settings
        """
        return {
            "timeout": cls.LEAD_GEN_TIMEOUT,
            "max_partners": cls.MAX_PARTNERS_PER_RUN
        }


# Load configuration on module import
try:
    ADKConfig.load()
except EnvironmentError as e:
    # Re-raise with additional context
    raise EnvironmentError(
        f"Failed to load ADK configuration: {str(e)}\n"
        f"Please ensure all required environment variables are set in backend/.env"
    ) from e


# Export configuration constants for easy access
GCP_PROJECT_ID = ADKConfig.GCP_PROJECT_ID
GCP_REGION = ADKConfig.GCP_REGION
GOOGLE_APPLICATION_CREDENTIALS = ADKConfig.GOOGLE_APPLICATION_CREDENTIALS

ADK_MODEL_FLASH = ADKConfig.ADK_MODEL_FLASH
ADK_MODEL_PRO = ADKConfig.ADK_MODEL_PRO

LEAD_GEN_TIMEOUT = ADKConfig.LEAD_GEN_TIMEOUT
RESEARCHER_TIMEOUT = ADKConfig.RESEARCHER_TIMEOUT
MAX_PARTNERS_PER_RUN = ADKConfig.MAX_PARTNERS_PER_RUN

GOOGLE_SEARCH_API_KEY = ADKConfig.GOOGLE_SEARCH_API_KEY
GOOGLE_SEARCH_ENGINE_ID = ADKConfig.GOOGLE_SEARCH_ENGINE_ID
DUCKDUCKGO_API_ENABLED = ADKConfig.DUCKDUCKGO_API_ENABLED
