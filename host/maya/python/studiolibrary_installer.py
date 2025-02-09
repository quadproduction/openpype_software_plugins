import sys
from pathlib import Path

plugin_name = "Studio Library"
plugin_version = "2.13.2"
plugin_package_path = Path("/prod/softprod/apps/studiolibrary/{}/linux".format(plugin_version))
plugin_install_script_name = "install.py"
plugin_package_script_path = plugin_package_path.joinpath(plugin_install_script_name)

def install():
    # First, add package to python path
    sys.path.append(str(plugin_package_path.joinpath("src").resolve()))

    # Now ensure the install script is called
    globals_dict = globals()
    globals_dict["__file__"] = plugin_package_script_path.resolve()

    exec(open(plugin_package_script_path).read(), globals_dict)
