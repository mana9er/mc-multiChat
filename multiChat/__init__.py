from .multiChat import MultiChatWS

# list dependencies
dependencies = ['mcBasicLib']


def load(logger, core):
    # Function "load" is required by mana9er-core.
    from os import path
    import json
    config_file = path.join(core.root_dir, 'multiChat', 'config.json')
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return MultiChatWS(logger, core, config)