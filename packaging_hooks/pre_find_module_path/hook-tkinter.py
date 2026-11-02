def pre_find_module_path(hook_api):
    # The bundled workspace Python has a valid Tk install, but PyInstaller's
    # isolated probe cannot see it. Keep normal module discovery enabled.
    return None
