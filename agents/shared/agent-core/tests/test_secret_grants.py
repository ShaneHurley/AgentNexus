import pytest
from agent_core.contracts import Grant, EffectiveGrant, ContractDenied, LAYERS

def test_secret_use_requires_all_layers():
    contract={"id":"dc:researcher","active":True,"leaf":True,"grant":{"secret_use":["provider/openrouter"]}}
    layers={name:{"secret_use":["provider/openrouter"]} for name in LAYERS}
    grant=EffectiveGrant.evaluate(contract,layers)
    grant.authorize("secret_use","provider/openrouter")
    layers["user"]={}
    with pytest.raises(ContractDenied):
        EffectiveGrant.evaluate(contract,layers).authorize("secret_use","provider/openrouter")

def test_legacy_grant_denies_secrets():
    assert Grant.from_mapping({}).secret_use == frozenset()
    with pytest.raises(ContractDenied): Grant.from_mapping({"secret_use":["*"]})
