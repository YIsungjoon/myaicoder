"""Tests for ModelsConfig YAML loading and environment detection."""

from pathlib import Path

from myaicoder.models.config import ModelsConfig


def test_load_defaults():
    """No config file → sensible defaults."""
    config = ModelsConfig.load("/nonexistent/path.yaml")
    assert config.environment == "dev"
    assert config.models_dir == "~/models"
    assert config.instances == []
    assert config.is_prod() is False


def test_load_dev_yaml(tmp_path: Path):
    """Load a dev environment config."""
    yaml_content = """
environment: dev
models_dir: "/tmp/test-models"
default_model: "small-model"
port: 9001

instances:
  - name: "small-model"
    file: "small.gguf"
    description: "A small model"
    vllm_args:
      gpu_memory_utilization: 0.5
      max_model_len: 4096
    defaults:
      temperature: 0.1
      max_tokens: 2048
  - name: "big-model"
    file: "big.gguf"
    description: "A big model"
"""
    config_path = tmp_path / "models.yaml"
    config_path.write_text(yaml_content)

    config = ModelsConfig.load(str(config_path))

    assert config.environment == "dev"
    assert config.models_dir == "/tmp/test-models"
    assert config.default_model == "small-model"
    assert config.port == 9001
    assert config.is_prod() is False
    assert len(config.instances) == 2

    small = config.get_profile("small-model")
    assert small is not None
    assert small.file == "small.gguf"
    assert small.vllm_args.gpu_memory_utilization == 0.5
    assert small.vllm_args.max_model_len == 4096
    assert small.defaults.temperature == 0.1
    assert small.defaults.max_tokens == 2048


def test_load_prod_yaml(tmp_path: Path):
    """Load a prod environment config with always_on and per-instance ports."""
    yaml_content = """
environment: prod
models_dir: "/data/models"

instances:
  - name: "model-a"
    file: "a.gguf"
    port: 8001
    always_on: true
  - name: "model-b"
    file: "b.gguf"
    port: 8002
    always_on: true
"""
    config_path = tmp_path / "prod.yaml"
    config_path.write_text(yaml_content)

    config = ModelsConfig.load(str(config_path))

    assert config.is_prod() is True
    assert len(config.instances) == 2
    assert config.instances[0].port == 8001
    assert config.instances[0].always_on is True
    assert config.instances[1].port == 8002


def test_get_profile_not_found():
    """Unknown profile name returns None."""
    config = ModelsConfig(instances=[])
    assert config.get_profile("nonexistent") is None


def test_get_default_profile():
    """Default profile resolution."""
    from myaicoder.models.config import ModelProfile

    p1 = ModelProfile(name="first", file="first.gguf")
    p2 = ModelProfile(name="second", file="second.gguf")

    # Explicit default
    config = ModelsConfig(default_model="second", instances=[p1, p2])
    assert config.get_default_profile() is not None
    assert config.get_default_profile().name == "second"

    # No explicit default → first instance
    config2 = ModelsConfig(instances=[p1, p2])
    assert config2.get_default_profile().name == "first"

    # Empty instances
    config3 = ModelsConfig(instances=[])
    assert config3.get_default_profile() is None


def test_gateway_fields(tmp_path: Path):
    """gateway_url and internal_token are loaded from YAML."""
    yaml_content = """
environment: dev
gateway_url: "http://localhost:8080"
internal_token: "secret-123"
instances: []
"""
    config_path = tmp_path / "models.yaml"
    config_path.write_text(yaml_content)

    config = ModelsConfig.load(str(config_path))
    assert config.gateway_url == "http://localhost:8080"
    assert config.internal_token == "secret-123"
