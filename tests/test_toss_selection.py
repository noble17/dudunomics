def test_fx_provider_uses_toss_when_market_data_provider_is_toss(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "toss")

    from core.fx import TossFxProvider, get_fx_provider

    assert isinstance(get_fx_provider(), TossFxProvider)
