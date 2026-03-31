import importlib
import warnings


def test_openai_api_shim_warns_and_reexports():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        module = importlib.import_module("openai_api")

    assert module.OpenAICog.__name__ == "OpenAICog"
    assert not hasattr(module, "OpenAIAPI")
    assert any(item.category is DeprecationWarning for item in caught)
