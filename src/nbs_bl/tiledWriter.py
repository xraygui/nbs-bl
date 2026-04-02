import os

def subscribe_tiled_profile(run_engine, config):
    from tiled.client import from_profile

    profile = config["profile"]
    api_key_env = config.get("api_key_env", None)
    catalog_path = config.get("catalog_path", [])
    subscribe_method = config.get("subscribe_method", "post_document")

    if api_key_env:
        api_key = os.environ[api_key_env]
    else:
        api_key = None

    if api_key is not None:
        client = from_profile(profile, api_key=api_key)
    else:
        client = from_profile(profile)
    for key in catalog_path:
        client = client[key]

    callback = getattr(client, subscribe_method)
    run_engine.subscribe(callback)
    return client

