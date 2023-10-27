Installation
============

**geoh5py** is currently written for Python 3.8 or higher, and depends on `NumPy <https://numpy.org/>`_ and
`h5py <https://www.h5py.org/>`_.



.. note:: Users will likely want to take advantage of other packages available in the Python ecosystem.
   We therefore recommend using `Miniforge <https://github.com/conda-forge/miniforge>`_ to handle the various packages.

Install **geoh5py** from PyPI::

    $ pip install geoh5py

To install the latest development version of **geoh5py**, you can use ``pip`` with the
latest GitHub ``development`` branch::

    $ pip install https://github.com/MiraGeoscience/geoh5py/archive/development.zip

To work with **geoh5py** source code in development, clone from GitHub and install in editable mode::

    $ git clone https://github.com/MiraGeoscience/geoh5py.git
    $ pip install -e ./geoh5py
