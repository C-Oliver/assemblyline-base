
import pytest
import warnings
import uuid

from datetime import datetime
from datemath import dm
from assemblyline.datastore import odm


@odm.model(index=True, store=True)
class BModel(odm.Model):
    depth = odm.Integer()
    width = odm.Integer()


@odm.model(index=True, store=True)
class AModel(odm.Model):
    flavour = odm.Text()
    height = odm.Integer()
    birthday = odm.Date()
    tags = odm.List(odm.Keyword())
    size = odm.Compound(BModel, default={'depth': 100, 'width': 100})


with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    test_map = {
        'test1': AModel(tags=['silly'], flavour='chocolate', height=100, birthday=dm('now-2d')),
        'test2': AModel(tags=['cats'], flavour='A little dry', height=180, birthday=dm('now-1d')),
        'test3': AModel(tags=['silly'], flavour='Red', height=140, birthday=dm('now'), size={'depth': 1, 'width': 1}),
        'test4': AModel(tags=['cats'], flavour='Bugs ++', height=30, birthday='2018-10-30T17:48:48+00:00'),
        'dict1': AModel(tags=['cats'], flavour='A--', height=300, birthday='2018-10-30T17:48:48Z'),
        'dict2': AModel(tags=[], flavour='100%', height=90, birthday=datetime.utcnow()),
        'dict3': AModel(tags=['10', 'cats'], flavour='', height=180, birthday=dm('now-3d')),
        'dict4': AModel(tags=['10', 'silly', 'cats'], flavour='blue', height=100, birthday=dm('now-1d')),
    }


def setup_store(docstore, request):
    try:
        ret_val = docstore.ping()
        if ret_val:
            collection_name = uuid.uuid4().hex
            docstore.register(collection_name, AModel)
            collection = docstore.__getattr__(collection_name)
            request.addfinalizer(collection.wipe)

            # cleanup
            for k in test_map.keys():
                collection.delete(k)

            for k, v in test_map.items():
                collection.save(k, v)

            # Commit saved data
            collection.commit()

            return collection
    except ConnectionError:
        pass
    return None


@pytest.fixture
def solr_connection(request):
    from assemblyline.datastore.stores.solr_store import SolrStore

    collection = setup_store(SolrStore(['127.0.0.1']), request)
    if collection:
        return collection

    return pytest.skip("Connection to the SOLR server failed. This test cannot be performed...")


@pytest.fixture
def es_connection(request):
    from assemblyline.datastore.stores.es_store import ESStore

    collection = setup_store(ESStore(['127.0.0.1']), request)
    if collection:
        return collection

    return pytest.skip("Connection to the Elasticsearch server failed. This test cannot be performed...")


@pytest.fixture
def riak_connection(request):
    from assemblyline.datastore.stores.riak_store import RiakStore

    collection = setup_store(RiakStore(['127.0.0.1']), request)
    if collection:
        return collection

    return pytest.skip("Connection to the Riak server failed. This test cannot be performed...")


# noinspection PyShadowingNames
def test_solr(solr_connection):
    if solr_connection:
        s_tc = solr_connection

        assert test_map.get('test1') == s_tc.get('test1')
        assert test_map.get('test2') == s_tc.get('test2')
        assert test_map.get('test3') == s_tc.get('test3')
        assert test_map.get('test4') == s_tc.get('test4')
        assert test_map.get('string') == s_tc.get('string')
        assert test_map.get('list') == s_tc.get('list')
        assert test_map.get('int') == s_tc.get('int')

        raw = [test_map.get('test1'), test_map.get('int'), test_map.get('test2')]
        ds_raw = s_tc.multiget(['test1', 'int', 'test2'])
        for item in ds_raw:
            raw.remove(item)
        assert len(raw) == 0

        test_keys = list(test_map.keys())
        for k in s_tc.keys():
            test_keys.remove(k)
        assert len(test_keys) == 0


# noinspection PyShadowingNames
def test_es(es_connection):
    if es_connection:
        s_tc = es_connection

        assert test_map.get('test1') == s_tc.get('test1')
        assert test_map.get('test2') == s_tc.get('test2')
        assert test_map.get('test3') == s_tc.get('test3')
        assert test_map.get('test4') == s_tc.get('test4')
        assert test_map.get('string') == s_tc.get('string')
        assert test_map.get('list') == s_tc.get('list')
        assert test_map.get('int') == s_tc.get('int')

        raw = [test_map.get('test1'), test_map.get('int'), test_map.get('test2')]
        ds_raw = s_tc.multiget(['test1', 'int', 'test2'])
        for item in ds_raw:
            raw.remove(item)
        assert len(raw) == 0

        test_keys = list(test_map.keys())
        for k in s_tc.keys():
            test_keys.remove(k)
        assert len(test_keys) == 0


# noinspection PyShadowingNames
def test_riak(riak_connection):
    if riak_connection:
        s_tc = riak_connection

        assert test_map.get('test1') == s_tc.get('test1')
        assert test_map.get('test2') == s_tc.get('test2')
        assert test_map.get('test3') == s_tc.get('test3')
        assert test_map.get('test4') == s_tc.get('test4')
        assert test_map.get('string') == s_tc.get('string')
        assert test_map.get('list') == s_tc.get('list')
        assert test_map.get('int') == s_tc.get('int')

        raw = [test_map.get('test1'), test_map.get('int'), test_map.get('test2')]
        ds_raw = s_tc.multiget(['test1', 'int', 'test2'])
        for item in ds_raw:
            raw.remove(item)
        assert len(raw) == 0

        test_keys = list(test_map.keys())
        for k in s_tc.keys():
            test_keys.remove(k)
        assert len(test_keys) == 0


# noinspection PyShadowingNames
def test_datastore_consistency(riak_connection, solr_connection, es_connection):
    if riak_connection and solr_connection and es_connection:

        def fix_date(data):
            # making date precision all the same throughout the datastores so we can compared them
            return {k.replace(".000", ""): v for k, v in data.items()}

        def fix_ids(data):
            # We're remapping all id fields to a default value so we can compare outputs
            data['items'] = [{'ID' if k in ["_id", '_yz_rk', '_id_'] else k: v
                              for k, v in item.items()}
                             for item in data['items']]
            return data

        def compare_output(solr, elastic, riak):
            errors = []

            if solr != riak:
                errors.append("solr != riak")

            if solr != elastic:
                errors.append("solr != elastic")

            if elastic != riak:
                errors.append("elastic != riak")

            if errors:
                print("\n\nNot all outputs are equal: {non_equal}\n\n"
                      "solr = {solr}\nelastic = {elastic}\nriak = {riak}\n\n".format(non_equal=", ".join(errors),
                                                                                     solr=solr,
                                                                                     elastic=elastic,
                                                                                     riak=riak))
                return False

            return True

        stores = {}
        s_tc = stores['solr'] = solr_connection
        e_tc = stores['elastic'] = es_connection
        r_tc = stores['riak'] = riak_connection

        try:
            assert compare_output(s_tc.get('list'), e_tc.get('list'), r_tc.get('list'))
            assert compare_output(s_tc.require('string'), e_tc.require('string'), r_tc.require('string'))
            assert compare_output(s_tc.get_if_exists('int'), e_tc.get_if_exists('int'), r_tc.get_if_exists('int'))
            for x in range(5):
                key = 'dict%s' % x
                assert compare_output(s_tc.get(key), e_tc.get(key), r_tc.get(key))
            assert compare_output(s_tc.multiget(['int', 'int']),
                                  e_tc.multiget(['int', 'int']),
                                  r_tc.multiget(['int', 'int']))
            assert compare_output(fix_ids(s_tc.search('*:*', sort="%s asc" % s_tc.datastore.ID)),
                                  fix_ids(e_tc.search('*:*', sort="%s asc" % e_tc.datastore.ID)),
                                  fix_ids(r_tc.search('*:*', sort="%s asc" % r_tc.datastore.ID)))
            assert compare_output(s_tc.search('*:*', offset=1, rows=1, filters="__access_lvl__:400",
                                              sort="%s asc" % s_tc.datastore.ID, fl='classification'),
                                  e_tc.search('*:*', offset=1, rows=1, filters="__access_lvl__:400",
                                              sort="%s asc" % e_tc.datastore.ID, fl='classification'),
                                  r_tc.search('*:*', offset=1, rows=1, filters="__access_lvl__:400",
                                              sort="%s asc" % r_tc.datastore.ID, fl='classification'))
            ss_s_list = list(s_tc.stream_search('classification:*', filters="__access_lvl__:400", fl='classification'))
            ss_e_list = list(e_tc.stream_search('classification:*', filters="__access_lvl__:400", fl='classification'))
            ss_r_list = list(r_tc.stream_search('classification:*', filters="__access_lvl__:400", fl='classification'))
            assert compare_output(ss_s_list, ss_e_list, ss_r_list)

            assert compare_output(sorted(list(s_tc.keys())), sorted(list(e_tc.keys())), sorted(list(r_tc.keys())))
            assert compare_output(s_tc.histogram('__access_lvl__', 0, 1000, 100, mincount=2),
                                  e_tc.histogram('__access_lvl__', 0, 1000, 100, mincount=2),
                                  r_tc.histogram('__access_lvl__', 0, 1000, 100, mincount=2))

            h_s = s_tc.histogram('__expiry_ts__',
                                 '{n}-10{d}/{d}'.format(n=s_tc.datastore.now, d=s_tc.datastore.day),
                                 '{n}+10{d}/{d}'.format(n=s_tc.datastore.now, d=s_tc.datastore.day),
                                 '+1{d}'.format(d=s_tc.datastore.day, mincount=2))
            h_e = e_tc.histogram('__expiry_ts__',
                                 '{n}-10{d}/{d}'.format(n=e_tc.datastore.now, d=e_tc.datastore.day),
                                 '{n}+10{d}/{d}'.format(n=e_tc.datastore.now, d=e_tc.datastore.day),
                                 '+1{d}'.format(d=e_tc.datastore.day, mincount=2))
            h_r = r_tc.histogram('__expiry_ts__',
                                 '{n}-10{d}/{d}'.format(n=r_tc.datastore.now, d=r_tc.datastore.day),
                                 '{n}+10{d}/{d}'.format(n=r_tc.datastore.now, d=r_tc.datastore.day),
                                 '+1{d}'.format(d=r_tc.datastore.day, mincount=2))
            assert compare_output(fix_date(h_s), fix_date(h_e), fix_date(h_r))
            assert compare_output(s_tc.field_analysis('classification'),
                                  e_tc.field_analysis('classification'),
                                  r_tc.field_analysis('classification'))

            assert compare_output(s_tc.grouped_search('__access_lvl__', fl='classification'),
                                  e_tc.grouped_search('__access_lvl__', fl='classification'),
                                  r_tc.grouped_search('__access_lvl__', fl='classification'))

            # TODO: fields are not of the same type in-between datastores does that matter?
            #       will print output for now without failing the test
            compare_output(s_tc.fields(), e_tc.fields(), r_tc.fields())

        finally:
            for store in stores.values():
                store.wipe()
