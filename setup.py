from setuptools import setup, find_packages

setup(
    name="medrxiv-langchain",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "langchain>=0.0.200",
        "requests>=2.28.0",
        "pandas>=1.5.0",
    ],
    author="Your Name",
    author_email="your.email@example.com",
    description="A LangChain loader for BioRxiv and MedRxiv papers",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/medrxiv-langchain",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
)
