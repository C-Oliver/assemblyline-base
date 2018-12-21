# This file contains the loaders for the different components of the system
from easydict import EasyDict
import os
import yaml

from assemblyline.common.importing import load_module_by_path


def get_classification(yml_config=None):
    from assemblyline.common.classification import Classification, InvalidDefinition

    if yml_config is None:
        yml_config = "/etc/assemblyline/classification.yml"

    classification_definition = {}
    default_file = os.path.join(os.path.dirname(__file__), "classification.yml")
    if os.path.exists(default_file):
        with open(default_file) as default_fh:
            default_yml_data = yaml.load(default_fh.read())
            if default_yml_data:
                classification_definition.update(default_yml_data)

    # Load modifiers from the yaml config
    if os.path.exists(yml_config):
        with open(yml_config) as yml_fh:
            yml_data = yaml.load(yml_fh.read())
            if yml_data:
                classification_definition.update(yml_data)

    if not classification_definition:
        raise InvalidDefinition('Could not find any classification definition to load.')

    return Classification(classification_definition)


def get_config(static=False, yml_config=None):
    from assemblyline.odm.models.config import Config

    if yml_config is None:
        yml_config = "/etc/assemblyline/config.yml"

    # Initialize a default config
    config = Config().as_primitives()

    # Load modifiers from the yaml config
    if os.path.exists(yml_config):
        with open(yml_config) as yml_fh:
            yml_data = yaml.load(yml_fh.read())
            if yml_data:
                config.update(yml_data)

    if not static:
        # TODO: Load a datastore object and load the config changes from the datastore
        # config.update(datastore_changes)
        pass
    return Config(config)


def get_constants(config=None):
    if config is None:
        config = get_config()
    return load_module_by_path(config.system.constants)


def get_datastore(config=None):
    if not config:
        config = get_config(static=True)

    if config.datastore.type == "elasticsearch":
        from assemblyline.datastore.stores.es_store import ESStore
        return ESStore(config.datastore.hosts)
    elif config.datastore.type == "riak":
        from assemblyline.datastore.stores.riak_store import RiakStore
        return RiakStore(config.datastore.hosts,
                         solr_port=config.datastore.riak.solr_port,
                         riak_http_port=config.datastore.riak.riak_http_port,
                         riak_pb_port=config.datastore.riak.riak_pb_port)
    elif config.datastore.type == "solr":
        from assemblyline.datastore.stores.solr_store import SolrStore
        return SolrStore(config.datastore.hosts, port=config.datastore.solr.port)
    else:
        from assemblyline.datastore.exceptions import DataStoreException
        raise DataStoreException(f"Invalid datastore type: {config.datastore.type}")


def get_dn_parser(config=None):
    if config is None:
        config = get_config()
    try:
        return load_module_by_path(config.auth.dn_parser)
    except ImportError:
        return None


def get_site_specific_apikey_handler(config=None):
    if config is None:
        config = get_config()
    return load_module_by_path(config.auth.apikey_handler)


def get_site_specific_dn_handler(config=None):
    if config is None:
        config = get_config()
    return load_module_by_path(config.auth.dn_handler)


def get_site_specific_userpass_handler(config=None):
    if config is None:
        config = get_config()
    return load_module_by_path(config.auth.userpass_handler)


def get_ui_context(config=None):
    if config is None:
        config = get_config()
    return EasyDict(load_module_by_path(config.ui.context))
