from locust import HttpUser, task, between

class InsightFlowReadLoad(HttpUser):
    """Anonymous health-check load. Authenticated scenarios can reuse the login cookie."""
    wait_time = between(0.5, 2)
    @task(3)
    def health(self): self.client.get("/api/health/", name="GET /api/health/")
    @task(1)
    def csrf(self): self.client.get("/api/csrf/", name="GET /api/csrf/")
