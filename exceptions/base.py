class AppError(Exception):
    status_code = 400
    default_message = "请求失败"
    headers: dict[str, str] | None = None

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)