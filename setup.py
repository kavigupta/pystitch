import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="permacache",
    version="3.6.2",
    author="Kavi Gupta, Matt Bowers",
    author_email="imperative-stitch@kavigupta.org",
    description="Imperative version of stitch.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kavigupta/imperative-stitch",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.9",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=["s-exp-parser==1.2.0"],
)
