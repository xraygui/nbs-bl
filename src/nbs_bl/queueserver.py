from .status import StatusDict, StatusContainerBase, RedisStatusDict, StatusList
from collections import abc
from ophyd import OphydObject
# import redis
from .redisUtils import open_redis_client_from_settings


class GlobalStatusManager:
    """
    Manager class for handling global status dictionaries and lists with Redis connections

    Parameters
    ----------
    redis_host : str, optional
        Redis server hostname, by default 'localhost'
    redis_port : int, optional
        Redis server port, by default 6379
    """

    def __init__(self, redis_host="localhost", redis_port=6379):
        self._status_dict = StatusDict()
        self._redis_client = None
        self._redis_host = redis_host
        self._redis_port = redis_port
        self._global_prefix = ""

    def init_redis(self, redis_settings):
        """
        Initialize Redis connection with optional new host/port and global prefix

        Parameters
        ----------
        host : str, optional
            Redis server hostname
        port : int, optional
            Redis server port
        global_prefix : str, optional
            Global prefix for all Redis keys, by default "status:"
        """
        self._redis_host = redis_settings.get("host", self._redis_host)
        self._redis_port = redis_settings.get("port", self._redis_port)

        self._global_prefix = redis_settings.get("prefix", self._global_prefix)
        self._redis_client = open_redis_client_from_settings(redis_settings)
        return self._redis_client

    def add_status(self, key, container: StatusContainerBase):
        """Add a status container to the manager"""
        self._status_dict[key] = container

    def remove_status(self, key):
        """Remove a status container from the manager"""
        del self._status_dict[key]

    def get_status(self):
        """Get dictionary of all status UIDs"""
        return {k: str(v.get_uid()) for k, v in self._status_dict.items()}

    def request_status_dict(self, key, use_redis=False, prefix=None):
        """
        Create and return a new status dictionary

        Parameters
        ----------
        key : str
            Key for the status dictionary
        use_redis : bool, optional
            If True, returns RedisStatusDict, otherwise StatusDict
        prefix : str, optional
            Additional prefix for Redis keys if using RedisStatusDict.
            If None, uses the key as prefix.

        Returns
        -------
        StatusDict or RedisStatusDict
            The requested status dictionary

        Raises
        ------
        RuntimeError
            If Redis is requested but not initialized
        """
        if use_redis:
            if self._redis_client is None:
                import warnings

                warnings.warn(f"Redis not initialized. Using plain StatusDict for {key} instead.")
                status_dict = StatusDict()
            else:
                # Construct the full prefix
                if prefix is None:
                    prefix = key
                full_prefix = f"{self._global_prefix}{prefix}"
                status_dict = RedisStatusDict(self._redis_client, prefix=full_prefix)
        else:
            status_dict = StatusDict()

        self.add_status(key, status_dict)
        return status_dict

    def request_status_list(self, key, use_redis=False):
        """
        Request a new status list, optionally backed by Redis

        Parameters
        ----------
        key : str
            Key for the status list
        use_redis : bool, optional
            If True, creates list in RedisStatusDict, otherwise returns plain StatusList

        Returns
        -------
        StatusList
            The requested status list

        Notes
        -----
        When using Redis, the list is stored in a RedisStatusDict using the global prefix,
        with the provided key used as the dictionary key for the list.
        """
        status_list = self._status_dict.get(key, None)
        if status_list is not None and not isinstance(status_list, StatusList):
            raise TypeError(f"Status key {key} already exists and is not a StatusList")

        if use_redis:
            if self._redis_client is None:
                import warnings

                warnings.warn(f"Redis not initialized. Using plain StatusList for {key} instead.")
                status_list = status_list or StatusList()
            else:
                redis_dict = self._get_or_create_redis_dict()
                if key in redis_dict:
                    values = redis_dict.get(key, []) or []
                    if isinstance(values, str):
                        values = [values]
                else:
                    values = list(status_list) if status_list is not None else []
                    redis_dict[key] = values
                if status_list is None:
                    status_list = StatusList(values)
                else:
                    status_list.clear()
                    status_list.extend(values)
        else:
            status_list = status_list or StatusList()

        self.add_status(key, status_list)
        return status_list

    def set_status_list(self, key, values, use_redis=False):
        """
        Replace a status list with new values.

        Parameters
        ----------
        key : str
            Key for the status list.
        values : iterable
            Values to store in the status list.
        use_redis : bool, optional
            If True, also write the full list value to Redis.

        Returns
        -------
        StatusList
            The updated status list.
        """
        status_list = self._status_dict.get(key, None)
        if status_list is not None and not isinstance(status_list, StatusList):
            raise TypeError(f"Status key {key} already exists and is not a StatusList")
        status_list = status_list or StatusList()
        if isinstance(values, str):
            values = [values]
        status_list.clear()
        status_list.extend(list(values))
        self.add_status(key, status_list)
        if use_redis and self._redis_client is not None:
            redis_dict = self._get_or_create_redis_dict()
            redis_dict[key] = list(status_list)
        return status_list

    def _get_or_create_redis_dict(self):
        """
        Get or create the global RedisStatusDict for storing lists

        Returns
        -------
        RedisStatusDict
            The global Redis dictionary for storing lists
        """
        # Use a special key for the global Redis dict
        global_dict_key = "_global_redis_dict"

        if global_dict_key not in self._status_dict:
            # Create new Redis dict with only global prefix
            redis_dict = RedisStatusDict(self._redis_client, prefix=self._global_prefix)
            self.add_status(global_dict_key, redis_dict)

        return self._status_dict[global_dict_key]

    def keys(self):
        return self._status_dict.keys()

    def __getitem__(self, key):
        return self._status_dict[key]

    def __setitem__(self, key, value):
        self.add_status(key, value)

    def __delitem__(self, key):
        self.remove_status(key)

    def __contains__(self, key):
        return key in self._status_dict

    def request_update(self, key):
        """Request an update for a specific status key"""
        if key in self._status_dict:
            sbuffer = self._status_dict[key]
            if isinstance(sbuffer, abc.Sequence):
                return represent_sequence(sbuffer)
            if isinstance(sbuffer, abc.Mapping):
                return represent_mapping(sbuffer)
            if isinstance(sbuffer, abc.Set):
                return represent_set(sbuffer)


# Create global instance
GLOBAL_USER_STATUS = GlobalStatusManager()


def request_update(key):
    return GLOBAL_USER_STATUS.request_update(key)


def get_status():
    return GLOBAL_USER_STATUS.get_status()


# Keep existing helper functions
def represent_item(item):
    if isinstance(item, OphydObject):
        return item.name
    elif isinstance(item, abc.Sequence):
        return represent_sequence(item)
    elif isinstance(item, abc.Mapping):
        return represent_mapping(item)
    elif isinstance(item, abc.Set):
        return represent_set(item)
    else:
        return item


def represent_mapping(m):
    rep = {}
    for k, v in m.items():
        rep[k] = represent_item(v)
    return rep


def represent_sequence(s):

    if isinstance(s, str):
        return s
    else:
        rep = []
        for v in s:
            rep.append(represent_item(v))
        return rep


def represent_set(s):
    return represent_sequence(s)


def print_mapping(m):
    return str(represent_mapping(m))


def print_sequence(s):
    return str(represent_sequence(s))


def print_set(s):
    return str(represent_set(s))
