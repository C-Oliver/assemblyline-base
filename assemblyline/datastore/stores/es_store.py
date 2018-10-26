import time

import elasticsearch
import elasticsearch.helpers
import json
import logging

from copy import copy, deepcopy
from datemath import dm
from datemath.helpers import DateMathException

from assemblyline.datastore import Collection, collection_reconnect, BaseStore, SearchException, \
    SearchRetryException, log
from assemblyline.datastore.support.elasticsearch.schemas import default_index, default_mapping


def parse_sort(sort):
    if isinstance(sort, list):
        return sort

    parts = sort.split(' ')
    if len(parts) == 1:
        return [parts]
    elif len(parts) == 2:
        if parts[1] not in ['asc', 'desc']:
            raise SearchException('Unknown sort parameter ' + sort)
        return [{parts[0]: parts[1]}]
    raise SearchException('Unknown sort parameter ' + sort)


class ESCollection(Collection):
    DEFAULT_SORT = [{'_id': 'asc'}]
    DEFAULT_SEARCH_FIELD = '__text__'
    MAX_SEARCH_ROWS = 500
    MAX_GROUP_LIMIT = 10
    MAX_FACET_LIMIT = 100
    DEFAULT_SEARCH_VALUES = {
        'timeout': None,
        'field_list': None,
        'facet_active': False,
        'facet_mincount': 1,
        'facet_fields': [],
        'filters': [],
        'group_active': False,
        'group_field': None,
        'group_sort': None,
        'group_limit': 1,
        'histogram_active': False,
        'histogram_field': None,
        'histogram_type': None,
        'histogram_gap': None,
        'histogram_mincount': 1,
        'start': 0,
        'rows': Collection.DEFAULT_ROW_SIZE,
        'query': "*",
        'sort': DEFAULT_SORT,
        'df': None
    }

    def __init__(self, datastore, name, model_class=None, replicas=0):
        self.replicas = replicas

        super().__init__(datastore, name, model_class=model_class)

    @collection_reconnect(log)
    def commit(self):
        self.datastore.client.indices.refresh(self.name)
        self.datastore.client.indices.clear_cache(self.name)
        return True

    @collection_reconnect(log)
    def multiget(self, key_list):
        # TODO: Need to find out how to leverage elastic's multiget
        #       For now lets use the default multiget
        return super().multiget(key_list)

    @collection_reconnect(log)
    def _get(self, key, retries):
        if retries is None:
            retries = self.RETRY_NONE

        done = False
        while not done:

            try:
                data = self.datastore.client.get(index=self.name, doc_type='_all', id=key)['_source']
                if "__non_doc_raw__" in data:
                    return data['__non_doc_raw__']
                return data
            except elasticsearch.exceptions.NotFoundError:
                if retries > 0:
                    time.sleep(0.05)
                    retries -= 1
                elif retries < 0:
                    time.sleep(0.05)
                else:
                    done = True

        return None

    def _save(self, key, data):
        if not isinstance(data, dict):
            saved_data = {'__non_doc_raw__': data}
        else:
            saved_data = data

        self.datastore.client.update(
            index=self.name,
            doc_type=self.name,
            id=key,
            body=json.dumps({'doc': saved_data, 'doc_as_upsert': True})
        )

    @collection_reconnect(log)
    def delete(self, key):
        try:
            info = self.datastore.client.delete(id=key, doc_type=self.name, index=self.name)
            return info['result'] == 'deleted'
        except elasticsearch.NotFoundError:
            return True

    @staticmethod
    def _to_python_datemath(value):
        replace_list = [
            (ESStore.DATE_FORMAT['NOW'], ESStore.DATEMATH_MAP['NOW']),
            (ESStore.DATE_FORMAT['YEAR'], ESStore.DATEMATH_MAP['YEAR']),
            (ESStore.DATE_FORMAT['MONTH'], ESStore.DATEMATH_MAP['MONTH']),
            (ESStore.DATE_FORMAT['WEEK'], ESStore.DATEMATH_MAP['WEEK']),
            (ESStore.DATE_FORMAT['DAY'], ESStore.DATEMATH_MAP['DAY']),
            (ESStore.DATE_FORMAT['HOUR'], ESStore.DATEMATH_MAP['HOUR']),
            (ESStore.DATE_FORMAT['MINUTE'], ESStore.DATEMATH_MAP['MINUTE']),
            (ESStore.DATE_FORMAT['SECOND'], ESStore.DATEMATH_MAP['SECOND']),
            (ESStore.DATE_FORMAT['DATE_END'], ESStore.DATEMATH_MAP['DATE_END'])
        ]

        for x in replace_list:
            value = value.replace(*x)

        return value

    # noinspection PyBroadException
    def _validate_steps_count(self, start, end, gap):
        gaps_count = None
        ret_type = None

        try:
            start = int(start)
            end = int(end)
            gap = int(gap)

            gaps_count = int((end - start) / gap)
            ret_type = int
        except ValueError:
            pass

        if not gaps_count:
            try:
                parsed_start = dm(self._to_python_datemath(start)).timestamp
                parsed_end = dm(self._to_python_datemath(end)).timestamp
                parsed_gap = dm(self._to_python_datemath(gap)).timestamp - dm('now').timestamp

                gaps_count = int((parsed_end - parsed_start) / parsed_gap)
                ret_type = str
            except DateMathException:
                pass

        if not gaps_count:
            raise SearchException(
                "Could not parse date ranges. (start='%s', end='%s', gap='%s')" % (start, end, gap))

        if gaps_count > self.MAX_FACET_LIMIT:
            raise SearchException('Facet max steps are limited to %s. '
                                  'Current settings would generate %s steps' % (self.MAX_FACET_LIMIT,
                                                                                gaps_count))
        return ret_type

    def _format_output(self, result, fields=None):
        source = result.get('fields', {})

        if isinstance(fields, str):
            fields = fields

        if fields is None or '*' in fields or self.datastore.ID in fields:
            source[self.datastore.ID] = result[self.datastore.ID]

        if fields is None or '*' in fields:
            return source

        return {key: val for key, val in source.items() if key in fields}

    def _cleanup_search_result(self, item):
        if isinstance(item, dict):
            item.pop('_source', None)
            item.pop('_version', None)
            item.pop(self.DEFAULT_SEARCH_FIELD, None)

        return item

    @collection_reconnect(log)
    def _search(self, args=None):
        parsed_values = deepcopy(self.DEFAULT_SEARCH_VALUES)

        for key, value in args:
            if key not in parsed_values:
                all_args = '; '.join('%s=%s' % (field_name, field_value) for field_name, field_value in args)
                raise ValueError("Unknown query argument: %s %s of [%s]" % (key, value, all_args))

            parsed_values[key] = value

        # This is our minimal query, the following sections will fill it out
        # with whatever extra options the search has been given.
        query_body = {
            "query": {
                "bool": {
                    "must": {
                        "query_string": {
                            "query": parsed_values['query']
                        }
                    }
                }
            },
            "stored_fields": parsed_values['field_list'] or ['*']
        }

        if parsed_values['df']:
            query_body["query"]["bool"]["must"]["query_string"]["default_field"] = parsed_values['df']

        # Time limit for the query
        if parsed_values['timeout']:
            query_body['timeout'] = parsed_values['timeout']

        # Add an histogram aggregation
        if parsed_values['histogram_active']:
            query_body["aggregations"] = query_body.get("aggregations", {})
            query_body["aggregations"]["histogram"] = {
                parsed_values['histogram_type']: {
                    "field": parsed_values['histogram_field'],
                    "interval": parsed_values['histogram_gap'],
                    "min_doc_count": parsed_values['histogram_mincount']
                }
            }

        # Add a facet aggregation
        if parsed_values['facet_active']:
            query_body["aggregations"] = query_body.get("aggregations", {})
            for field in parsed_values['facet_fields']:
                query_body["aggregations"][field] = {
                    "terms": {
                        "field": field,
                        "min_doc_count": parsed_values['facet_mincount']
                    }
                }

        # Add a group aggregation
        if parsed_values['group_active']:
            query_body["aggregations"] = query_body.get("aggregations", {})
            for field in [parsed_values['group_field']]:
                query_body["aggregations"]['group-' + field] = {
                    "terms": {
                        "field": field,
                    },
                    "aggregations": {
                        "groupings": {
                            "top_hits": {
                                "sort": parsed_values['group_sort'] or [{field: 'asc'}],
                                "size": parsed_values['group_limit'],
                                "stored_fields": parsed_values['field_list'] or ['*']
                            }
                        }
                    }
                }

        # Parse the sort string into the format elasticsearch expects
        if parsed_values['sort']:
            query_body['sort'] = parse_sort(parsed_values['sort'])

        # Add an offset/number of results for simple paging
        if parsed_values['start']:
            query_body['from'] = parsed_values['start']
        if parsed_values['rows']:
            query_body['size'] = parsed_values['rows']

        # Add filters
        if 'filter' not in query_body['query']['bool']:
            query_body['query']['bool']['filter'] = []

        if isinstance(parsed_values['filters'], str):
            query_body['query']['bool']['filter'].append({'query_string': {'query': parsed_values['filters']}})
        else:
            query_body['query']['bool']['filter'].extend({'query_string': {'query': ff}}
                                                         for ff in parsed_values['filters'])

        try:
            # Run the query
            result = self.datastore.client.search(index=self.name, body=json.dumps(query_body))
            return result

        except elasticsearch.RequestError:
            raise

        except (elasticsearch.TransportError, elasticsearch.ConnectionError, elasticsearch.ConnectionTimeout) as error:
            raise SearchRetryException("collection: %s, query: %s, error: %s" % (self.name, query_body, str(error)))

        except Exception as error:
            raise SearchException("collection: %s, query: %s, error: %s" % (self.name, query_body, str(error)))

    def search(self, query, offset=0, rows=None, sort=None,
               fl=None, timeout=None, filters=(), access_control=None):

        if not rows:
            rows = self.DEFAULT_ROW_SIZE

        if not sort:
            sort = self.DEFAULT_SORT

        args = [
            ('query', query),
            ('start', offset),
            ('rows', rows),
            ('sort', sort),
            ('df', self.DEFAULT_SEARCH_FIELD)
        ]

        if fl:
            field_list = fl.split(',')
            args.append(('field_list', field_list))
        else:
            field_list = None

        if timeout:
            args.append(('timeout', "%sms" % timeout))

        if access_control:
            if not filters:
                filters = [access_control]
            else:
                if isinstance(filters, list):
                    filters.append(access_control)
                else:
                    filters = [filters] + [access_control]

        if filters:
            args.append(('filters', filters))

        result = self._search(args)

        docs = [self._format_output(doc, field_list) for doc in result['hits']['hits']]
        output = {
            "offset": int(offset),
            "rows": int(rows),
            "total": int(result['hits']['total']),
            "items": [self._cleanup_search_result(x) for x in docs]
        }
        return output

    def stream_search(self, query, fl=None, filters=(), access_control=None, item_buffer_size=200):
        if item_buffer_size > 500 or item_buffer_size < 50:
            raise SearchException("Variable item_buffer_size must be between 50 and 500.")

        if query in ["*", "*:*"] and fl != self.datastore.ID:
            raise SearchException("You did not specified a query, you just asked for everything... Play nice.")

        if fl:
            fl = fl.split(',')

        query_body = {
            "query": {
                "bool": {
                    "must": {
                        "query_string": {
                            "default_field": self.datastore.ID,
                            "query": query
                        }
                    },
                    'filter': []
                }
            },
            "stored_fields": fl or ['*']
        }

        # Add a filter query to the search
        if access_control:
            query_body['query']['bool']['filter'].append({'query_string': {'query': access_control}})

        if isinstance(filters, str):
            query_body['query']['bool']['filter'].append({'query_string': {'query': filters}})
        else:
            query_body['query']['bool']['filter'].extend({'query_string': {'query': ff}} for ff in filters)

        iterator = elasticsearch.helpers.scan(
            self.datastore.client,
            query=query_body,
            index=self.name,
            doc_type=self.name,
            preserve_order=True
        )

        for value in iterator:
            # Unpack the results, ensure the id is always set
            yield self._format_output(value, fl)

    def keys(self, access_control=None):
        for item in self.stream_search("%s:*" % self.datastore.ID, fl=self.datastore.ID, access_control=access_control):
            yield item[self.datastore.ID]

    @collection_reconnect(log)
    def histogram(self, field, start, end, gap, query="*", mincount=1, filters=None, access_control=None):
        type_modifier = self._validate_steps_count(start, end, gap)

        if not filters:
            filters = []
        elif isinstance(filters, str):
            filters = [filters]
        filters.append('{field}:[{min} TO {max}]'.format(field=field, min=start, max=end))

        args = [
            ('query', query),
            ('histogram_active', True),
            ('histogram_field', field),
            ('histogram_type', "date_histogram" if isinstance(gap, str) else 'histogram'),
            ('histogram_gap', gap.strip('+') if isinstance(gap, str) else gap),
            ('histogram_mincount', mincount)
        ]

        if access_control:
            filters.append(access_control)

        if filters:
            args.append(('filters', filters))

        result = self._search(args)

        # Convert the histogram into a dictionary
        return {type_modifier(row.get('key_as_string', row['key'])): row['doc_count']
                for row in result['aggregations']['histogram']['buckets']}

    @collection_reconnect(log)
    def field_analysis(self, field, query="*", prefix=None, contains=None, ignore_case=False, sort=None, limit=10,
                       min_count=1, filters=None, access_control=None):
        if not filters:
            filters = []
        elif isinstance(filters, str):
            filters = [filters]

        args = [
            ('query', query),
            ('facet_active', True),
            ('facet_fields', [field]),
            ('facet_mincount', min_count)
        ]

        # TODO: prefix, contains, ignore_case, sort

        if access_control:
            filters.append(access_control)

        if filters:
            args.append(('filters', filters))

        result = self._search(args)

        # Convert the histogram into a dictionary
        return {row.get('key_as_string', row['key']): row['doc_count']
                for row in result['aggregations'][field]['buckets']}

    @collection_reconnect(log)
    def grouped_search(self, group_field, query="*", offset=0, sort=None, group_sort=None, fl=None, limit=1,
                       rows=None, filters=(), access_control=None):

        if not rows:
            rows = self.DEFAULT_ROW_SIZE

        args = [
            ('query', query),
            ('group_active', True),
            ('group_field', group_field),
            ('group_limit', limit),
            ('group_sort', group_sort),
            ('start', offset),
            ('rows', rows),
            ('sort', sort)
        ]

        # TODO: offset and row don't seem to get applied to the grouping

        if fl:
            field_list = fl.split(',')
            args.append(('field_list', field_list))
        else:
            field_list = None

        if access_control:
            if not filters:
                filters = [access_control]
            else:
                if isinstance(filters, list):
                    filters.append(access_control)
                else:
                    filters = [filters] + [access_control]

        if filters:
            args.append(('filters', filters))

        result = self._search(args)

        group_docs = result['aggregations']['group-%s' % group_field]['buckets']

        return {
            'offset': offset,
            'rows': rows,
            'total': len(group_docs),
            'items': [{
                'value': grouping['key'],
                'total': grouping['doc_count'],
                'items': [self._cleanup_search_result(self._format_output(row, field_list))
                          for row in grouping['groupings']['hits']['hits']]
            } for grouping in group_docs[offset:offset+rows]]
        }

    @collection_reconnect(log)
    def fields(self):
        def flatten_fields(props):
            out = {}
            for name, value in props.items():
                if 'properties' in value:
                    for child, ctype in flatten_fields(value['properties']).items():
                        out[name + '.' + child] = ctype
                elif 'type' in value:
                    out[name] = value['type']
                else:
                    raise ValueError("Unknown field data " + str(props))
            return out

        data = self.datastore.client.indices.get(self.name)

        properties = flatten_fields(data[self.name]['mappings'][self.name].get('properties', {}))

        collection_data = {}

        for p_name, p_val in properties.items():
            if p_name.startswith("_") or "//" in k:
                continue
            if not Collection.FIELD_SANITIZER.match(k):
                continue

            collection_data[p_name] = {
                "indexed": True,
                "stored": True,
                "list": True,
                "type": p_val
            }

        return collection_data

    @collection_reconnect(log)
    def _ensure_collection(self):
        if not self.datastore.client.indices.exists(self.name):
            log.warning("Collection {collection} does not exists. "
                        "Creating it now...".format(collection=self.name.upper()))
            index = deepcopy(default_index)
            mappings = deepcopy(default_mapping)
            if 'settings' not in index:
                index['settings'] = {}
            if 'index' not in index['settings']:
                index['settings']['index'] = {}
            index['settings']['index']['number_of_replicas'] = self.replicas

            # TODO: build schema from model
            index['mappings'][self.name] = mappings
            self.datastore.client.indices.create(self.name, index)

    @collection_reconnect(log)
    def wipe(self):
        log.warning("Wipe operation started for collection: %s" % self.name.upper())

        if self.datastore.client.indices.exists(self.name):
            self.datastore.client.indices.delete(self.name)


class ESStore(BaseStore):
    """ Elasticsearch implementation of the ResultStore interface."""
    ID = '_id'
    DEFAULT_SORT = "_id asc"
    DATE_FORMAT = {
        'NOW': 'now',
        'YEAR': 'y',
        'MONTH': 'M',
        'WEEK': 'w',
        'DAY': 'd',
        'HOUR': 'h',
        'MINUTE': 'm',
        'SECOND': 's',
        'MILLISECOND': 'ms',
        'MICROSECOND': 'micros',
        'NANOSECOND': 'nanos',
        'SEPARATOR': '||',
        'DATE_END': 'Z'
    }

    def __init__(self, hosts, collection_class=ESCollection):
        super(ESStore, self).__init__(hosts, collection_class)
        tracer = logging.getLogger('elasticsearch')
        tracer.setLevel(logging.CRITICAL)

        self.client = elasticsearch.Elasticsearch(hosts=hosts, connection_class=elasticsearch.RequestsHttpConnection)

        self.url_path = 'elastic'

    def __str__(self):
        return '{0} - {1}'.format(self.__class__.__name__, self._hosts)

    def ping(self):
        return self.client.ping()

    def close(self):
        super().close()
        self.client = None

    def connection_reset(self):
        self.client = elasticsearch.Elasticsearch(hosts=self._hosts,
                                                  connection_class=elasticsearch.RequestsHttpConnection)


if __name__ == "__main__":
    from pprint import pprint

    s = ESStore(['127.0.0.1'])
    s.register('user')
    s.user.delete('sgaron')
    s.user.delete('bob')
    s.user.delete('robert')
    s.user.delete('denis')

    s.user.save('sgaron', {'__expiry_ts__': '2018-10-10T16:26:42.961Z', 'uname': 'sgaron',
                           'is_admin': True, '__access_lvl__': 400, 'classification': "U"})
    s.user.save('bob', {'__expiry_ts__': '2018-10-21T16:26:42.961Z', 'uname': 'bob',
                        'is_admin': False, '__access_lvl__': 100, 'classification': "U"})
    s.user.save('denis', {'__expiry_ts__': '2018-10-19T16:26:42.961Z', 'uname': 'denis',
                          'is_admin': False, '__access_lvl__': 100, 'classification': "TS"})
    s.user.save('robert', {'__expiry_ts__': '2018-10-19T16:26:42.961Z', 'uname': 'robert',
                           'is_admin': False, '__access_lvl__': 200, 'classification': "C"})

    s.user.save('string', 'a')
    s.user.save('list', ['a', 'b', 1])
    s.user.save('int', 1)

    s.user.commit()

    print('\n# multiget string, list, int')
    pprint(s.user.multiget(['string', 'list', 'int']))

    print('\n# get sgaron')
    pprint(s.user.get('sgaron'))
    print('\n# get bob')
    pprint(s.user.get('bob'))

    print('\n# multiget sgaron, robert, denis')
    pprint(s.user.multiget(['sgaron', 'robert', 'denis']))

    print('\n# search *:*')
    pprint(s.user.search("*:*"))

    print('\n# search __expiry_ts__ all fields')
    pprint(s.user.search('__expiry_ts__:"2018-10-19T16:26:42.961Z"', filters="__access_lvl__:100", fl="*"))

    print('\n# stream keys')
    for k in s.user.keys():
        print(k)

    print('\n# histogram number')
    pprint(s.user.histogram('__access_lvl__', 0, 1000, 100, mincount=2))

    print('\n# histogram date')
    pprint(s.user.histogram('__expiry_ts__', 'now-1M/d', 'now+1d/d', '+1d'))

    print('\n# field analysis')
    pprint(s.user.field_analysis('__access_lvl__'))

    print('\n# grouped search')
    pprint(s.user.grouped_search(s.ID, rows=2, offset=1, sort='%s asc' % s.ID))
    pprint(s.user.grouped_search('__access_lvl__', sort='__access_lvl__ asc', fl=s.ID))
    pprint(s.user.grouped_search('__access_lvl__', rows=2, offset=1, sort='__access_lvl__ asc', fl=s.ID))

    print('\n# fields')
    pprint(s.user.fields())

    s.user.wipe()
    # print(s.user._search([('q', "*:*")]))
    # print(s.user._search([('q', "*:*"), ('fl', "*")]))
