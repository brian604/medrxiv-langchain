from setuptools import setup, find_packages

setup(
    name="medrxiv-langchain",
    version="1.1.0",
    packages=find_packages(),
    install_requires=[
        "langchain>=0.0.200",
        "requests>=2.28.0",
        "pandas>=1.5.0",
    ],
    extras_require={
        "api": [
            "fastapi>=0.104.0",
            "uvicorn[standard]>=0.24.0",
            "pydantic>=2.0.0",
            "python-multipart>=0.0.6",
            "sentence-transformers>=2.2.0",
            "openai>=1.0.0",
            "aiofiles>=23.0.0",
        ],
        "telegram": [
            "python-telegram-bot>=20.0",
        ],
        "all": [
            "fastapi>=0.104.0",
            "uvicorn[standard]>=0.24.0",
            "pydantic>=2.0.0",
            "python-multipart>=0.0.6",
            "sentence-transformers>=2.2.0",
            "openai>=1.0.0",
            "aiofiles>=23.0.0",
            "python-telegram-bot>=20.0",
        ],
    },
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
