import unittest
from unittest.mock import patch

from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.auth.security import get_current_user, get_optional_current_user


test_app = FastAPI()


@test_app.get("/optional-auth")
def optional_auth_route(
    current_user: dict | None = Depends(get_optional_current_user),
):
    return {"user": current_user}


@test_app.get("/required-auth")
def required_auth_route(current_user: dict = Depends(get_current_user)):
    return {"user": current_user}


class AuthSecurityCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(test_app)

    def test_optional_auth_ignores_invalid_token(self) -> None:
        with patch(
            "app.auth.security._resolve_user_from_token",
            side_effect=HTTPException(status_code=401, detail="访问令牌已过期"),
        ):
            response = self.client.get(
                "/optional-auth",
                headers={"Authorization": "Bearer expired-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"user": None})

    def test_required_auth_rejects_invalid_token(self) -> None:
        with patch(
            "app.auth.security._resolve_user_from_token",
            side_effect=HTTPException(status_code=401, detail="访问令牌已过期"),
        ):
            response = self.client.get(
                "/required-auth",
                headers={"Authorization": "Bearer expired-token"},
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "访问令牌已过期")

    def test_required_auth_accepts_valid_token(self) -> None:
        user = {"id": "user-1", "primary_auth_method": "password"}
        with patch("app.auth.security._resolve_user_from_token", return_value=user):
            response = self.client.get(
                "/required-auth",
                headers={"Authorization": "Bearer valid-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"user": user})


if __name__ == "__main__":
    unittest.main()