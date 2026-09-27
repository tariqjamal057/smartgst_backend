import time
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent / "request_log.txt"


class RequestTrackerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.time()
        response = self.get_response(request)
        duration_ms = int((time.time() - started) * 1000)
        query = request.META.get("QUERY_STRING", "")
        authed = "Bearer" in request.META.get("HTTP_AUTHORIZATION", "")
        line = (
            f"{time.strftime('%H:%M:%S')} {request.method} {request.path}?{query} "
            f"{response.status_code} {duration_ms}ms auth={authed}"
        )
        try:
            with LOG.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass
        return response
