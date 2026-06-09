from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AssessmentError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class DocumentParseError(AssessmentError):
    def __init__(self, message: str):
        super().__init__(message, status_code=422)


class UnsupportedFileTypeError(DocumentParseError):
    pass


class FileTooLargeError(AssessmentError):
    def __init__(self, max_mb: int):
        super().__init__(f"File exceeds {max_mb} MB limit", status_code=413)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AssessmentError)
    async def assessment_error_handler(request: Request, exc: AssessmentError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"message": exc.message, "type": type(exc).__name__},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"message": "An unexpected error occurred", "type": "InternalServerError"},
        )
