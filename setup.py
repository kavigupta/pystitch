import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="imperative_stitch",
    version="3.6.4",
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
        "s-exp-parser==1.3.1",
        "datasets==2.10.1",
        "ast_scope>=0.4.0",
        # my fork of python-graphs, update this to the latest commit hash
        "python-graphs @ https://github.com/kavigupta/python-graphs/archive/5eb4c7e30622b6cd24973431d2678209d48bd1ed.zip",
    ],
)
