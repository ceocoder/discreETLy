import re
import os
import yaml

def clean_dag_id(dag_id):
    return re.sub('_v?[0-9]+.[0-9]+$', '', dag_id)


def handle_resource(resource, value = None):
    def check_optional(func):
        def func_wrapper(self, *args, **kwargs):
            return func(self, *args, **kwargs) if self.__dict__.get(resource) else value
        return func_wrapper
    return check_optional

def simple_state(state):
    if state in ('success', 'failed'):
        return state
    else: # simplifies statuses like "queued", "up_for_retry", etc
        return 'running'

def load_data_provider(classname, params):
    try:
        parts = classname.split('.')
        module = __import__('.'.join(parts[:-1]))
        for comp in parts[1:]:
            module = getattr(module, comp)
        return module(**params)
    except Exception as e:
        raise Exception(f'Could not instantiate the provided TABLE_DESCRIPTION_SERVICE: {classname}', e)

def get_yaml_file_content(path):
    config_file = path
    if os.path.exists(config_file):
        with open(config_file, 'r') as file:
            return yaml.load(file)
    else:
        return None