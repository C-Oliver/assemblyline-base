import redis
import json

from assemblyline.remote.datatypes import get_client, retry_call

h_pop_script = """
local result = redis.call('hget', ARGV[1], ARGV[2])
if result then redis.call('hdel', ARGV[1], ARGV[2]) end
return result
"""


class Hash(object):
    def __init__(self, name, host=None, port=None, db=None):
        if isinstance(host, redis.Redis):
            self.c = host
        else:
            self.c = get_client(host, port, db, False)
        self.name = name
        self._pop = self.c.register_script(h_pop_script)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.delete()

    def add(self, key, value):
        if isinstance(key, bytes):
            raise ValueError("Cannot use bytes for hashmap keys")
        return retry_call(self.c.hsetnx, self.name, key, json.dumps(value))

    def exists(self, key):
        return retry_call(self.c.hexists, self.name, key)

    def get(self, key):
        item = retry_call(self.c.hget, self.name, key)
        if not item:
            return item
        return json.loads(item)

    def keys(self):
        return [k.decode('utf-8') for k in retry_call(self.c.hkeys, self.name)]

    def length(self):
        return retry_call(self.c.hlen, self.name)

    def items(self):
        items = retry_call(self.c.hgetall, self.name)
        if not isinstance(items, dict):
            return {}
        for k in items.keys():
            items[k] = json.loads(items[k])
        return {k.decode('utf-8'): v for k, v in items.items()}

    def pop(self, key):
        item = retry_call(self._pop, args=[self.name, key])
        if not item:
            return item
        return json.loads(item)

    def set(self, key, value):
        if isinstance(key, bytes):
            raise ValueError("Cannot use bytes for hashmap keys")
        return retry_call(self.c.hset, self.name, key, json.dumps(value))

    def delete(self):
        retry_call(self.c.delete, self.name)


class ExpiringHash(Hash):
    def __init__(self, name, ttl=86400, host=None, port=None, db=None):
        super(ExpiringHash, self).__init__(name, host, port, db)
        self.ttl = ttl

    def add(self, key, value):
        rval = super(ExpiringHash, self).add(key, value)
        retry_call(self.c.expire, self.name, self.ttl)
        return rval

    def set(self, key, value):
        rval = super(ExpiringHash, self).set(key, value)
        retry_call(self.c.expire, self.name, self.ttl)
        return rval
