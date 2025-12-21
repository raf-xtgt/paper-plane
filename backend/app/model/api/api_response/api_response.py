from pydantic import BaseModel
from typing import Any, Generic, TypeVar, Union
from enum import Enum

class ResponseStatus(str, Enum):
    OK_RESPONSE = "OK_RESPONSE"
    ERROR = "ERROR"

T = TypeVar('T')

class ApiResponse(BaseModel, Generic[T]):
    status: ResponseStatus
    data: T

    @classmethod
    def success(cls, data: T) -> 'ApiResponse[T]':
        """Create a successful API response."""
        return cls(status=ResponseStatus.OK_RESPONSE, data=data)
    
    @classmethod
    def error(cls, data: T) -> 'ApiResponse[T]':
        """Create an error API response."""
        return cls(status=ResponseStatus.ERROR, data=data)