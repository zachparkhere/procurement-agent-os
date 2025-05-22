from setuptools import setup, find_packages

setup(
    name="po_agent_os",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "pydantic-settings",
        "python-dotenv",
        "supabase",
        "openai",
        "asyncio",
    ],
) 