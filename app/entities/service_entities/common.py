from pydantic import BaseModel

__all__ = (
    'ValidationRule',
    'ValidationRules',
    'ValidationResult',
    'ValidationResults',
)


class ValidationRule(BaseModel):
    name: str
    rule: str


class ValidationRules(BaseModel):
    rules: list[ValidationRule]


class ValidationResult(BaseModel):
    match: bool = False


class ValidationResults(BaseModel):
    results: list[ValidationResult]
