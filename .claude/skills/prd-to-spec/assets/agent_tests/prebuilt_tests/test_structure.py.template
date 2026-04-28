"""Tests for agent file structure and module validity."""

import pytest
import yaml


@pytest.mark.structure
class TestRequiredFiles:
    """Test that all required files exist."""

    def test_agent_directory_exists(self, agent_path):
        """Test that the generated_agent directory exists."""
        assert agent_path.exists(), f"Agent directory not found: {agent_path}"
        assert agent_path.is_dir(), f"Agent path is not a directory: {agent_path}"

    def test_app_directory_exists(self, agent_app_path):
        """Test that the app directory exists."""
        assert agent_app_path.exists(), f"App directory not found: {agent_app_path}"
        assert agent_app_path.is_dir(), f"App path is not a directory: {agent_app_path}"

    def test_requirements_txt_exists(self, agent_path):
        """Test that requirements.txt exists."""
        req_file = agent_path / "requirements.txt"
        assert req_file.exists(), "requirements.txt is missing"
        assert req_file.stat().st_size > 0, "requirements.txt is empty"

    def test_asset_yaml_exists(self, agent_path):
        """Test that asset.yaml exists."""
        app_yaml = agent_path / "asset.yaml"
        assert app_yaml.exists(), "asset.yaml is missing"
        assert app_yaml.stat().st_size > 0, "asset.yaml is empty"


@pytest.mark.structure
class TestAssetYaml:
    """Test asset.yaml configuration."""

    def test_asset_yaml_is_valid_yaml(self, agent_path):
        """Test that asset.yaml is valid YAML."""
        app_yaml = agent_path / "asset.yaml"

        try:
            with open(app_yaml, "r", encoding="utf-8") as f:
                yaml.safe_load(f)
        except yaml.YAMLError as e:
            pytest.fail(f"asset.yaml is not valid YAML: {e}")

    def test_asset_yaml_has_required_fields(self, agent_path):
        """Test that asset.yaml has required fields."""
        app_yaml = agent_path / "asset.yaml"

        with open(app_yaml, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        assert config is not None, "asset.yaml is empty"
        assert "kind" in config, "asset.yaml should have kind 'Asset' (capital A)"
        assert config["kind"] == "Asset", "asset.yaml should have kind 'Asset' (capital A)"
        assert "type" in config, "asset.yaml should have type"
        assert config["type"] == "agent", "asset.yaml should have type 'agent'"
