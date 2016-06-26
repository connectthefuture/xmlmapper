from setuptools import setup

setup(
    name='xmlmapper',
    version='0.1',
    url='https://github.com/ldpl/xmlmapper',
    author='Pavel Stupnikov',
    author_email='pavel.stupnikov@gmail.com',
    description='Module for mapping data from various xml sources '
        'to common data model',
    packages=['xmlmapper'],
    install_requires=[
        'lxml>=3.6',
        'six>=1.10',
    ],
)
