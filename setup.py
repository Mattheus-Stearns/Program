from setuptools import setup, find_packages

setup(
    name="camp_scheduler",
    version="0.1",
    packages=find_packages(),
    package_data={
        'camp_scheduler': ['data/*'],
    },
    install_requires=[
        'pandas',
    ],
    python_requires='>=3.6',
)