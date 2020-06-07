import setuptools
from distutils.core import setup, Extension

_swizzle = Extension('demo',
                    define_macros = [('MAJOR_VERSION', '1'),
                                     ('MINOR_VERSION', '0')],
                    include_dirs = ['/usr/local/include'],
                    libraries = [],
                    library_dirs = ['/usr/local/lib'],
                    sources = ['_swizzle.c'])

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="bntx",
    version="0.0.1",
    author="Emelia and \'AboodXD\'",
    author_email="2634959+baconwaifu@users.noreply.github.com",
    description="Nintendo BNTX library and tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/baconwaifu/BNTX-Extractor",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.4',
    ext_modules=[_swizzle]
)

