from .status import StatusDict, StatusContainerBase, RedisStatusDict, StatusList
from collections import abc
from ophyd import OphydObject
import redis


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
        self._global_prefix = None

    def init_redis(self, host=None, port=None, db=0, global_prefix="status:"):
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
        if host is not None:
            self._redis_host = host
        if port is not None:
            self._redis_port = port

        self._global_prefix = global_prefix
        print(f"Initializing redis Client with {host}, {port}, {db}")
        self._redis_client = redis.Redis(
            host=self._redis_host, port=self._redis_port, db=db
        )
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
        Request a new status dictionary

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

                warnings.warn("Redis not initialized. Using plain StatusDict instead.")
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
        if use_redis:
            if self._redis_client is None:
                import warnings

                warnings.warn("Redis not initialized. Using plain StatusList instead.")
                status_list = StatusList()
            else:
                # Create or get the Redis dict with only global prefix
                redis_dict = self._get_or_create_redis_dict()
                # Create new status list
                status_list = StatusList()
                # Store in Redis dict under the given key
                redis_dict[key] = status_list
        else:
            status_list = StatusList()

        # Add to status manager
        self.add_status(key, status_list)
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
