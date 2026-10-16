class OfficeError(Exception):
    """A refusal or failure with a stable code the panel can show. Never carries cell values."""

    def __init__(self, code, detail="", status=400):
        self.code, self.detail, self.status = code, detail, status
        super().__init__(f"{code}: {detail}")
