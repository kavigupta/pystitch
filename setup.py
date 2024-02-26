import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="imperative_stitch",
    version="3.6.13",
    author="Kavi Gupta, Matt Bowers",
    author_email="imperative-stitch@kavigupta.org",
    description="Imperative version of stitch.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kavigupta/imperative-stitch",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.8",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "datasets==2.10.1",
        "ast_scope>=0.4.2",
        "permacache>=3.7.0",
        "frozendict==2.3.8",
        # my fork of python-graphs, update this to the latest commit hash
        "python-graphs @ https://github.com/kavigupta/python-graphs/archive/693b2bc5e65a0f930617d75c3fb0c1750d35a622.zip",
        "neurosym==0.0.17",
    ],
)
