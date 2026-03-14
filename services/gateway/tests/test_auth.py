from __future__ import annotations

from app.auth import AuthStore
from app.config import GatewayConfig

from .conftest import TEST_API_KEY, make_test_config


class TestAuthStore:
    def setup_method(self):
        self.config = make_test_config()
        self.store = AuthStore(self.config)

    def test_authenticate_valid_key(self):
        user = self.store.authenticate(TEST_API_KEY)
        assert user is not None
        assert user.user_id == "test_user"
        assert user.name == "테스트 사용자"
        assert user.role == "admin"

    def test_authenticate_invalid_key(self):
        user = self.store.authenticate("wrong-key")
        assert user is None

    def test_authenticate_empty_key(self):
        user = self.store.authenticate("")
        assert user is None

    def test_hash_key_deterministic(self):
        h1 = AuthStore.hash_key("my-secret")
        h2 = AuthStore.hash_key("my-secret")
        assert h1 == h2
        assert h1.startswith("sha256:")

    def test_hash_key_different_inputs(self):
        h1 = AuthStore.hash_key("key-a")
        h2 = AuthStore.hash_key("key-b")
        assert h1 != h2

    def test_empty_config(self):
        store = AuthStore(GatewayConfig())
        user = store.authenticate("anything")
        assert user is None
