from setuptools import setup, find_packages

setup(
    name="vendor_email_logger_agent",
    version="0.1.0",
    packages=find_packages(include=['vendor_email_logger_agent*']),
    install_requires=[
        "supabase",
        "python-dotenv",
        "google-api-python-client",
        "google-auth-httplib2",
        "google-auth-oauthlib",
        "PyPDF2",
    ],
    python_requires=">=3.8",
) 