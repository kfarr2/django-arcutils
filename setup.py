#!/usr/bin/env python
from setuptools import setup

setup(
    name="django-arcutils",
    version='0.0.1',
    url='https://github.com/PSU-OIT-ARC/django-arcutils',
    author='Matt Johnson',
    author_email='mdj2@pdx.edu',
    description="ARC Utils for Django sites",
    packages=['arcutils'],
    zip_safe=False,
    classifiers=[
        'Framework :: Django',
    ],
    include_package_data=True,
    extras_require={
        'ldap': ['python3-ldap'],
        'test': ['python3-ldap', 'model_mommy', 'mock', 'django'],
        'logging': ['python-logstash'],
    }
)
