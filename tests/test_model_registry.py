from pathlib import Path

from contract_risk_analyzer.modeling import registry


class DummyModel:
    pass


def test_local_model_loader_caches_by_resolved_path(monkeypatch, tmp_path: Path) -> None:
    model_path = tmp_path / "model.joblib"
    model_path.write_text("placeholder", encoding="utf-8")
    calls = {"count": 0}

    def fake_load(path: str) -> DummyModel:
        calls["count"] += 1
        return DummyModel()

    registry.clear_model_cache()
    monkeypatch.setattr(registry.TfidfLogisticBaseline, "load", staticmethod(fake_load))

    first = registry.load_local_model(model_path)
    second = registry.load_local_model(str(model_path))

    assert first is second
    assert calls["count"] == 1
    registry.clear_model_cache()


def test_load_legalpro_model_uses_env_or_default(monkeypatch) -> None:
    calls = []

    def fake_load_classifier(config_path: str, fallback_on_failure: bool):
        calls.append(config_path)
        return DummyModel()

    monkeypatch.setattr("contract_risk_analyzer.modeling.legalpro.load_legalpro_classifier", fake_load_classifier)
    registry.clear_model_cache()

    monkeypatch.delenv("CONTRACT_RISK_MODEL_CONFIG", raising=False)
    m1 = registry.load_legalpro_model()
    assert m1 is not None
    assert Path(calls[-1]) == Path("configs/ledgar_sra.yaml")

    monkeypatch.setenv("CONTRACT_RISK_MODEL_CONFIG", "configs/legalpro.yaml")
    registry.clear_model_cache()
    m2 = registry.load_legalpro_model()
    assert m2 is not None
    assert Path(calls[-1]) == Path("configs/legalpro.yaml")
    registry.clear_model_cache()

