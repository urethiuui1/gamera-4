#!/usr/bin/env python
# -*- mode: python; indent-tabs-mode: nil; tab-width: 3 -*-
# vim: set tabstop=3 shiftwidth=3 expandtab:
#
# Copyright (C) 2001-2005 Ichiro Fujinaga, Michael Droettboom, Karl MacMillan
#               2010-2012 Christoph Dalitz
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
import datetime
import glob
import multiprocessing
import os
import platform
from distutils.ccompiler import CCompiler
from distutils.command.build_ext import build_ext

import sys

# # unfortunately this does not help installing data_files
# # to the same dir as gamera :(
# for scheme in INSTALL_SCHEMES.values():
#     scheme['data'] = scheme['purelib']

# sys.exit(0)

if sys.hexversion < 0x03050000:
    print("At least Python 3.5 is required to build Gamera.  You have")
    print(sys.version)
    sys.exit(1)

cross_compiling = False

# We do this first, so that when gamera.__init__ loads gamera.__version__,
# it is in fact the new and updated version
gamera_version = open("version", 'r').readlines()[0].strip()
has_openmp = None
no_wx = False
i = 0
for argument in sys.argv:
    i = i + 1
    if argument == "--dated_version":
        d = datetime.date.today()
        monthstring = str(d.month)
        daystring = str(d.day)
        if d.month < 10:
            monthstring = '0' + monthstring
        if d.day < 10:
            daystring = '0' + daystring
        gamera_version = "2_nightly_%s%s%s" % (d.year, monthstring, daystring)
        sys.argv.remove(argument)
        break
    elif argument == '--compiler=mingw32_cross':
        sys.argv[sys.argv.index('--compiler=mingw32_cross')] = '--compiler=mingw32'
        cross_compiling = True
    elif argument == '--openmp=yes':
        has_openmp = True
        sys.argv.remove(argument)
    elif argument == '--openmp=no':
        has_openmp = False
        sys.argv.remove(argument)
    elif argument == '--nowx':
        no_wx = True
        sys.argv.remove(argument)
open("gamera/__version__.py", "w").write("ver = '%s'\n\n" % gamera_version)
print("Gamera version:", gamera_version)

# query OpenMP (parallelization) support and save it to compile time config file
if has_openmp is None:
    has_openmp = False
    if platform.system() == "Linux":
        p = os.popen("gcc -dumpversion", "r")
        gccv = p.readline().strip().split(".")
        p.close()
        if int(gccv[0]) > 4 or (int(gccv[0]) == 4 and int(gccv[1]) >= 3):
            has_openmp = True
f = open("gamera/__compiletime_config__.py", "w")
f.write("# automatically generated configuration at compile time\n")
if has_openmp:
    f.write("has_openmp = True\n")
    print("Compiling genetic algorithms with parallelization (OpenMP)")
else:
    f.write("has_openmp = False\n")
    print("Compiling genetic algorithms without parallelization (OpenMP)")
f.close()

from distutils.core import setup, Extension
from gamera import gamera_setup

##########################################
# generate the command line startup scripts
command_line_utils = (
    ('gamera_gui', 'gamera_gui.py',
     """#!%(executable)s
%(header)s
print("Loading GAMERA...")
print("Use 'gamera_gui --help' to display command line options") 
import sys
try:
    from gamera.config import config
    from gamera.gui import gui
    config.parse_args(sys.argv[1:])
    gui.run()
except Exception as e:
    if not isinstance(e, (SystemExit, KeyboardInterrupt)):
      import traceback
      import textwrap
      print("Gamera made the following fatal error:")
      print()
      print(textwrap.fill(str(e)))
      print()
      print("=" * 75)
      print("The traceback is below.  Please send this to the Gamera developers")
      print("if you feel you got here in error.")
      print("-" * 75)
    """),)

if sys.platform == 'win32':
    command_line_filename_at = 1
    scripts_directory_name = "Scripts"
else:
    command_line_filename_at = 0
    scripts_directory_name = "bin/"

info = {'executable': sys.executable,
        'header':
            """# This file was automatically generated by the\n"""
            """# Gamera setup script on %s.\n""" % sys.platform}
for util in command_line_utils:
    if sys.platform == 'win32':
        _, file, content = util
    else:
        file, _, content = util
    fd = open(file, 'w')
    fd.write(content % info)
    fd.close()
os.chmod(file, 0o700)

scripts = [x[command_line_filename_at] for x in command_line_utils] + ['gamera_post_install.py']

##########################################
# generate the plugins
plugin_extensions = []
plugins = gamera_setup.get_plugin_filenames('gamera/plugins/')
plugin_extensions = gamera_setup.generate_plugins(
    plugins, "gamera.plugins", True)

########################################
# Non-plugin extensions

eodev_files = glob.glob("src/eodev/*.cpp") + glob.glob("src/eodev/*/*.cpp")
eodev_dir = glob.glob("src/eodev/*")
eodev_includes = ["src/eodev"]
for entry in eodev_dir:
    if os.path.isdir(entry):
        eodev_includes.append(entry)

graph_files = glob.glob("src/graph/*.cpp") + glob.glob("src/graph/graphmodule/*.cpp")
kdtree_files = ["src/geostructs/kdtreemodule.cpp", "src/geostructs/kdtree.cpp"]

# libstdc++ does not exist with MS VC, but is linke dby default
if ('--compiler=mingw32' not in sys.argv) and (sys.platform == 'win32'):
    galibraries = []
else:
    galibraries = ["stdc++"]
if has_openmp:
    ExtGA = Extension("gamera.knnga",
                      ["src/knnga/knnga.cpp", "src/knnga/knngamodule.cpp"] + eodev_files,
                      include_dirs=["include", "src"] + eodev_includes,
                      libraries=galibraries,
                      extra_compile_args=gamera_setup.extras['extra_compile_args'] + ["-fopenmp"],
                      extra_link_args=["-fopenmp"]
                      )
else:
    ExtGA = Extension("gamera.knnga",
                      ["src/knnga/knnga.cpp", "src/knnga/knngamodule.cpp"] + eodev_files,
                      include_dirs=["include", "src"] + eodev_includes,
                      libraries=galibraries,
                      extra_compile_args=gamera_setup.extras['extra_compile_args']
                      )

extensions = [Extension("gamera.gameracore",
                        ["src/gameracore/gameramodule.cpp",
                         "src/gameracore/sizeobject.cpp",
                         "src/gameracore/pointobject.cpp",
                         "src/gameracore/floatpointobject.cpp",
                         "src/gameracore/dimobject.cpp",
                         "src/gameracore/rectobject.cpp",
                         "src/gameracore/regionobject.cpp",
                         "src/gameracore/regionmapobject.cpp",
                         "src/gameracore/rgbpixelobject.cpp",
                         "src/gameracore/imagedataobject.cpp",
                         "src/gameracore/imageobject.cpp",
                         "src/gameracore/imageinfoobject.cpp",
                         "src/gameracore/iteratorobject.cpp"
                         ],
                        include_dirs=["include"],
                        **gamera_setup.extras,
                        ),
              Extension("gamera.knncore",
                        ["src/knncore/knncoremodule.cpp"],
                        include_dirs=["include", "src"],
                        **gamera_setup.extras
                        ),
              ExtGA,
              Extension("gamera.graph", graph_files,
                        include_dirs=["include", "src", "include/graph", "src/graph/graphmodule"],
                        **gamera_setup.extras),
              Extension("gamera.kdtree", kdtree_files,
                        include_dirs=["include", "src", "include/geostructs"],
                        **gamera_setup.extras)]
extensions.extend(plugin_extensions)

##########################################
# Here's the basic distutils stuff

# read versions from compile computer
pythonversion = "%d.%d" % (sys.version_info[0], sys.version_info[1])
if not no_wx:
    import wx

    wx_version_info = wx.__version__.split(".")
    wxversion = "%s.%s" % (wx_version_info[0], wx_version_info[1])
    description = ("This is the Gamera installer.\n" +
                   "\tPlease ensure that Python " + pythonversion +
                   " and wxPython " + wxversion + "\n" +
                   "\tare installed before proceeding.")
else:
    description = ("This is the Gamera installer.\n" +
                   "\tPlease ensure that Python " + pythonversion +
                   "\tare installed before proceeding.")

includes = [(os.path.join(gamera_setup.include_path, path),
             glob.glob(os.path.join("include", os.path.join(path, ext))))
            for path, ext in
            [("", "*.hpp"),
             ("plugins", "*.hpp"),
             ("vigra", "*.hxx"),
             ("geostructs", "*.hpp"),
             ("graph", "*.hpp")]]

srcfiles = [(os.path.join(gamera_setup.lib_path, path),
             glob.glob(os.path.join(path, ext)))
            for path, ext in
            [("src/geostructs", "*.cpp"), ("src/graph", "*.cpp")]]

packages = ['gamera', 'gamera.gui', 'gamera.gui.gaoptimizer', 'gamera.plugins',
            'gamera.toolkits', 'gamera.backport']

if sys.hexversion >= 0x02040000:
    data_files = includes
    package_data = {"gamera": ["test/*.tiff"]}
else:
    data_files = [(os.path.join(gamera_setup.lib_path, "$LIB/test"),
                   glob.glob("gamera/test/*.tiff"))] + includes
    package_data = {}

data_files += srcfiles

if sys.platform == 'darwin':
    packages.append("gamera.mac")

# https://stackoverflow.com/a/13176803
# multithreading building
try:
    from concurrent.futures import ThreadPoolExecutor as Pool
except ImportError:
    from multiprocessing.pool import ThreadPool as LegacyPool

    # To ensure the with statement works. Required for some older 2.7.x releases
    class Pool(LegacyPool):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()
            self.join()


def build_extensions(self):
    """Function to monkey-patch
    distutils.command.build_ext.build_ext.build_extensions

    """
    self.check_extensions_list(self.extensions)

    try:
        num_jobs = os.cpu_count()
    except AttributeError:
        num_jobs = multiprocessing.cpu_count()

    with Pool(num_jobs) as pool:
        pool.map(self.build_extension, self.extensions)


def compile(self, sources, output_dir=None, macros=None, include_dirs=None, debug=0, extra_preargs=None,
            extra_postargs=None, depends=None):
    """Function to monkey-patch distutils.ccompiler.CCompiler"""
    macros, objects, extra_postargs, pp_opts, build = self._setup_compile(
        output_dir, macros, include_dirs, sources, depends, extra_postargs
    )
    cc_args = self._get_cc_args(pp_opts, debug, extra_preargs)

    for obj in objects:
        try:
            src, ext = build[obj]
        except KeyError:
            continue
        self._compile(obj, src, ext, cc_args, extra_postargs, pp_opts)

    # Return *all* object filenames, not just the ones we just built.
    return objects


build_ext.build_extensions = build_extensions
CCompiler.compile = compile

setup(cmdclass=gamera_setup.cmdclass,
      name="gamera",
      version=gamera_version,
      url="http://gamera.sourceforge.net/",
      author="Michael Droettboom and Christoph Dalitz",
      author_email="gamera-devel@yahoogroups.com",
      ext_modules=extensions,
      description=description,
      packages=packages,
      scripts=scripts,
      package_data=package_data,
      data_files=data_files,
      )
