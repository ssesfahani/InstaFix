# setup.py
from Cython.Build import cythonize
from setuptools import Extension, setup

# Define the extension module
extensions = [
    Extension(
        "js_string",  # The name of the extension module
        ["js_string.pyx"],  # The Cython source file
        extra_compile_args=["-O3", "-march=native"],  # Optimization flags
    )
]

# Setup configuration
setup(
    name="js_string",
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            "language_level": "3",  # Use Python 3 syntax
            "boundscheck": False,  # Disable bounds checking globally
            "wraparound": False,  # Disable negative indexing globally
            "cdivision": True,  # Disable division-by-zero checking globally
        },
    ),
    zip_safe=False,
)
