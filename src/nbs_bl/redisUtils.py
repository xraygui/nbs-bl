from nslsii.utils import open_redis_client

def open_redis_client_from_settings(settings):
    default_port = 6380 if settings.get("ssl", False) else 6379
    return open_redis_client(
        redis_url=settings["host"],
        redis_port=settings.get("port", default_port),
        redis_ssl=settings.get("ssl", False),
        redis_db=settings.get("db", 0),
    )