import os

def subscribe_tiled_profile(run_engine, config):
    if "profile" in config:
        from tiled.client import from_profile as create_client
        client_args = [config['profile'],]
    elif "uri" in config:
        from tiled.client import from_uri as create_client
        client_args = [config['uri'],]
    else:
        raise ValueError("Invalid configuration for tiled writer")
    api_key_env = config.get("api_key_env", None)
    catalog_path = config.get("catalog_path", [])
    subscribe_method = config.get("subscribe_method", "post_document")

    if api_key_env:
        api_key = os.environ[api_key_env]
    else:
        api_key = None

    if api_key is not None:
        client = create_client(*client_args, api_key=api_key)
    else:
        client = create_client(*client_args)
    for key in catalog_path:
        client = client[key]

    if subscribe_method == "post_document":
        callback = client.post_document
    elif subscribe_method == "tiled_writer":
        from bluesky_tiled_plugins import TiledWriter
        callback = TiledWriter(client)
    else:
        raise ValueError(f"Invalid subscribe method: {subscribe_method}")
    run_engine.subscribe(callback)
    return client

