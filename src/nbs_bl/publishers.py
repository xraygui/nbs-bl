import os

def publish_to_tiled(run_engine, config, print_substep=print):
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

def publish_to_kafka(run_engine, config, print_substep=print):
    from nslsii import configure_kafka_publisher

    name = config.get("name")
    kafka_file = config.get("config_file", None)
    print_substep(f"Publishing to Kafka topic: {name}")
    if kafka_file is not None:
        configure_kafka_publisher(run_engine, name, override_config_path=kafka_file)
    else:
        configure_kafka_publisher(run_engine, name)

def publish_to_zmq(run_engine, config, print_substep=print):
    from bluesky.callbacks.zmq import Publisher, Proxy

    hostname = config.get("hostname", "localhost")
    port = config.get("port", 5577)
    start_proxy = config.get("start_proxy", False)
    if start_proxy:
        output_port = config.get("output_port", 5578)
        print_substep(f"Starting ZMQ proxy on {port} and forwarding to {output_port}")
        Proxy(port, output_port)
    publisher = Publisher(f"{hostname}:{port}")
    run_engine.subscribe(publisher)
