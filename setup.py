"""A setuptools based setup module.
See:
https://packaging.python.org/guides/distributing-packages-using-setuptools/
https://github.com/pypa/sampleproject
"""

from setuptools import setup, find_packages


install_requires = list()
with open("requirements.txt") as f:
    install_requires = [line for line in f]


setup(
    name="vault",
    version="0.1.0",
    description="Vault Digital Preservation Service",
    url="https://git.archive.org/dps/vault-site",
    author="Web Team",
    # When your source code is in a subdirectory under the project root, e.g.
    # `src/`, it is necessary to specify the `package_dir` argument.
    package_dir={
        "vault": "vault",
        "vault_site": "vault_site",
    },
    packages=find_packages(),
    python_requires=">=3.8, <4",
    install_requires=install_requires,
    # If there are data files included in your packages that need to be
    # installed, specify them here.
    package_data={
        "vault": [
            "migrations/*.py",
            "sql/*.sql",
            "static/**/*",
            "static/*",
        ],
    },
    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # `pip` to create the appropriate form of executable for the target
    # platform.
    #
    # For example, the following would provide a command called `sample` which
    # executes the function `main` from this package when invoked:
    entry_points={
        "console_scripts": [
            "process_hashed_files=vault.utilities.process_hashed_files:main",
            "process_chunked_files=vault.utilities.process_chunked_files:main",
        ],
    },
    project_urls={
        "Source": "https://git.archive.org/dps/vault-site",
    },
)
