"""OPA Client implementation supporting HTTP communication and local evaluator fallback."""

import logging
from typing import Any, Dict
import httpx

from app.core.config import get_settings
from app.rules.opa.base import BaseOPAClient
from app.rules.opa.evaluator import LocalRegoEvaluator

logger = logging.getLogger("app.rules.opa")


class HTTPOPAClient(BaseOPAClient):
    """
    Client for evaluating policies via OPA's HTTP REST API (`/v1/data/{policy_path}`).
    Falls back gracefully to LocalRegoEvaluator if OPA daemon is unreachable.
    """

    def __init__(self, base_url: str, timeout: int = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def evaluate_policy(
        self,
        policy_path: str,
        input_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        url_path = policy_path.replace(".", "/")
        endpoint = f"{self.base_url}/v1/data/{url_path}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    json={"input": input_data},
                )
                if response.status_code == 200:
                    data = response.json()
                    result = data.get("result", {})
                    if isinstance(result, dict) and "result" in result:
                        return result
                    elif isinstance(result, str):
                        return {"result": result, "explanation": {}}
                logger.warning(
                    "OPA returned non-200 or unexpected structure (%s): %s. Falling back to local evaluator.",
                    response.status_code,
                    response.text,
                )
        except Exception as exc:
            logger.info("OPA HTTP endpoint unreachable (%s). Using local deterministic evaluator.", str(exc))

        # Safe deterministic local fallback
        return LocalRegoEvaluator.evaluate(input_data)


def get_opa_client() -> BaseOPAClient:
    """Factory returning configured OPA Client."""
    settings = get_settings()
    return HTTPOPAClient(base_url=settings.OPA_URL, timeout=settings.OPA_TIMEOUT_SECONDS)
