"""Abstract base class for OPA policy evaluation."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseOPAClient(ABC):
    """Abstract interface for OPA policy evaluation."""

    @abstractmethod
    async def evaluate_policy(
        self,
        policy_path: str,
        input_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Evaluate a policy in OPA with the provided structured input.
        Returns dictionary containing 'result' ('ELIGIBLE', 'NOT_ELIGIBLE', 'MANUAL_REVIEW')
        and 'explanation'.
        """
        pass
